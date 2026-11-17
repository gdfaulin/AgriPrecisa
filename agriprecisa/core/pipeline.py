# -*- coding: utf-8 -*-
"""
AgriPrecisa: IDW -> vector grid -> zonal statistics workflow.

Shared by the step-by-step wizard (menu/toolbar) and by the Processing
algorithm, so both produce exactly the same result.
"""

import math
import os

from osgeo import gdal
from qgis import processing
from qgis.core import (
    QgsCoordinateTransform, QgsFeatureRequest, QgsGeometry, QgsRectangle, QgsPointXY,
    QgsProcessingException, QgsProcessingMultiStepFeedback, QgsProcessingUtils, QgsVectorLayer,
    QgsGraduatedSymbolRenderer, QgsClassificationJenks, QgsStyle, QgsFillSymbol,
    QgsFeature, QgsField, QgsFields, QgsVectorFileWriter, QgsCoordinateTransformContext,
)

from .compat import UNIT_METERS, WRITER_NO_ERROR, FIELD_INT
from .idw_math import (NODATA, idw_grid, safe_name, snap_extent, unique_prefixes,
                       MIN_NEIGHBOURS, DEFAULT_MAX_NEIGHBOURS)
from .paths import shapefile_field_names
from ..i18n import tr, fmt

N_CLASSES = 5
COLOR_RAMP = "RdYlGn"


# ---------------------------------------------------------------------------
# Helpers that accept either a QgsVectorLayer or a QgsProcessingFeatureSource
# ---------------------------------------------------------------------------
def crs_of(source):
    return source.sourceCrs() if hasattr(source, "sourceCrs") else source.crs()


def name_of(source):
    return source.sourceName() if hasattr(source, "sourceName") else source.name()


def crs_in_meters(crs):
    """True when the CRS is projected and its unit is metres."""
    return crs.isValid() and not crs.isGeographic() and crs.mapUnits() == UNIT_METERS


def rect_to_crs(rect, src_crs, dst_crs, transform_context):
    if src_crs == dst_crs or not src_crs.isValid() or not dst_crs.isValid():
        return QgsRectangle(rect)
    ct = QgsCoordinateTransform(src_crs, dst_crs, transform_context)
    return ct.transformBoundingBox(rect)


def buffered(rect, distance):
    return QgsRectangle(rect.xMinimum() - distance, rect.yMinimum() - distance,
                        rect.xMaximum() + distance, rect.yMaximum() + distance)


def features_extent(features):
    """Bounding box of an iterable of features (None if there is no geometry)."""
    ext = None
    for f in features:
        g = f.geometry()
        if g is None or g.isEmpty():
            continue
        bb = g.boundingBox()
        if ext is None:
            ext = QgsRectangle(bb)
        else:
            ext.combineExtentWith(bb)
    return ext


def count_points(source, rect, rect_crs, transform_context):
    """Number of point features of ``source`` inside ``rect`` (given in ``rect_crs``)."""
    r = rect_to_crs(rect, rect_crs, crs_of(source), transform_context)
    req = QgsFeatureRequest().setFilterRect(r).setNoAttributes()
    return sum(1 for _ in source.getFeatures(req))


def extract_points(source, field, rect, rect_crs, transform_context):
    """Coordinates (in ``rect_crs``) and valid numeric values of ``field`` inside ``rect``."""
    src_crs = crs_of(source)
    ct = None
    if src_crs != rect_crs:
        ct = QgsCoordinateTransform(src_crs, rect_crs, transform_context)
    req = QgsFeatureRequest().setFilterRect(rect_to_crs(rect, rect_crs, src_crs, transform_context))
    req.setSubsetOfAttributes([field], source.fields())

    xs, ys, zs = [], [], []
    for feat in source.getFeatures(req):
        try:
            value = float(feat[field])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(value):
            continue
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            continue
        geom = QgsGeometry(geom)
        if ct is not None:
            geom.transform(ct)
        points = geom.asMultiPoint() if geom.isMultipart() else [geom.asPoint()]
        for p in points:
            if rect.contains(p):
                xs.append(p.x())
                ys.append(p.y())
                zs.append(value)
    return xs, ys, zs


def boundary_geometry(features):
    """Union of the boundary geometries (None if there is none)."""
    geoms = [QgsGeometry(f.geometry()) for f in features
             if f.geometry() is not None and not f.geometry().isEmpty()]
    if not geoms:
        return None
    geom = QgsGeometry.unaryUnion(geoms) if len(geoms) > 1 else geoms[0]
    return geom.makeValid() if not geom.isGeosValid() else geom


def sample_stats(source, fields, boundary_geom, boundary_crs, search_rect, transform_context):
    """
    Count samples of a point layer for the wizard.

    Returns {"inside": n, "used": n, "fields": {name: {"inside": n, "used": n}}}:
      inside -> points inside the boundary polygon (field values: non-empty numbers)
      used   -> points inside the search rectangle (boundary + tolerance), i.e. the
                samples the interpolation will use
    """
    src_crs = crs_of(source)
    ct = None
    if src_crs != boundary_crs:
        ct = QgsCoordinateTransform(src_crs, boundary_crs, transform_context)
    req = QgsFeatureRequest().setFilterRect(
        rect_to_crs(search_rect, boundary_crs, src_crs, transform_context))
    req.setSubsetOfAttributes(list(fields), source.fields())

    engine = QgsGeometry.createGeometryEngine(boundary_geom.constGet())
    engine.prepareGeometry()

    stats = {"inside": 0, "used": 0, "fields": {f: {"inside": 0, "used": 0} for f in fields}}
    for feat in source.getFeatures(req):
        geom = feat.geometry()
        if geom is None or geom.isEmpty():
            continue
        geom = QgsGeometry(geom)
        if ct is not None:
            geom.transform(ct)
        if not search_rect.intersects(geom.boundingBox()):
            continue
        inside = engine.intersects(geom.constGet())
        stats["used"] += 1
        stats["inside"] += int(inside)
        for f in fields:
            try:
                ok = math.isfinite(float(feat[f]))
            except (TypeError, ValueError):
                ok = False
            if ok:
                stats["fields"][f]["used"] += 1
                stats["fields"][f]["inside"] += int(inside)
    return stats


def field_cell_centres(boundary_geom, max_side=90):
    """
    Centres of a coarse grid (about ``max_side`` cells on the longest side) that fall
    inside the field. Used to measure the coverage distance of each attribute.
    Returns (xs, ys, grid, mask) with grid = (xmin, ymax, ncol, nrow, res).
    """
    import numpy as np
    bb = boundary_geom.boundingBox()
    res = max(max(bb.width(), bb.height()) / max_side, 0.5)
    xmin, ymin, xmax, ymax, ncol, nrow = snap_extent(
        bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum(), res)
    engine = QgsGeometry.createGeometryEngine(boundary_geom.constGet())
    engine.prepareGeometry()
    mask = np.zeros((nrow, ncol), dtype=bool)
    for r in range(nrow):
        y = ymax - (r + 0.5) * res
        for c in range(ncol):
            # keep a reference to the point geometry while GEOS uses it (a temporary
            # QgsGeometry is freed too early and the test always returned False)
            pt = QgsGeometry.fromPointXY(QgsPointXY(xmin + (c + 0.5) * res, y))
            mask[r, c] = engine.intersects(pt.constGet())
    rows, cols = np.nonzero(mask)
    return xmin + (cols + 0.5) * res, ymax - (rows + 0.5) * res, (xmin, ymax, ncol, nrow, res), mask


def edge_distances(boundary_geom, xs, ys):
    """Distance of each sample to the field border; -1 for samples outside the field."""
    import numpy as np
    engine = QgsGeometry.createGeometryEngine(boundary_geom.constGet())
    engine.prepareGeometry()
    border = QgsGeometry(boundary_geom.constGet().boundary())
    out = np.full(len(xs), -1.0)
    for k, (x, y) in enumerate(zip(xs, ys)):
        pt = QgsGeometry.fromPointXY(QgsPointXY(float(x), float(y)))
        if engine.intersects(pt.constGet()):
            out[k] = border.distance(pt)
    return out


def write_geotiff(path, array, xmin, ymax, res, crs):
    nrow, ncol = array.shape
    ds = gdal.GetDriverByName("GTiff").Create(
        path, ncol, nrow, 1, gdal.GDT_Float32, options=["COMPRESS=DEFLATE"])
    if ds is None:
        raise QgsProcessingException(tr("err_create_file", path=path))
    ds.SetGeoTransform((xmin, res, 0.0, ymax, 0.0, -res))
    ds.SetProjection(crs.toWkt())
    band = ds.GetRasterBand(1)
    band.SetNoDataValue(NODATA)
    band.WriteArray(array.astype("float32"))
    band.FlushCache()
    ds = None


def style_graduated(layer, field, classes=N_CLASSES, ramp_name=COLOR_RAMP):
    """Graduated renderer: Jenks natural breaks, RdYlGn ramp, no outline."""
    symbol = QgsFillSymbol.createSimple({"outline_style": "no"})
    ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
    renderer = QgsGraduatedSymbolRenderer(field)
    renderer.setSourceSymbol(symbol)
    if ramp is not None:
        renderer.setSourceColorRamp(ramp)
    renderer.setClassificationMethod(QgsClassificationJenks())
    renderer.updateClasses(layer, classes)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


# ---------------------------------------------------------------------------
# Job description and execution
# ---------------------------------------------------------------------------
RASTER_MARGIN = 100.0   # metres added around the boundary for the interpolated rasters


# ---------------------------------------------------------------------------
# Standard grid: only an ID numbered 1, 2, 3... and one column per attribute
# ---------------------------------------------------------------------------
GRID_ID_FIELD = "id"
# columns that native:creategrid adds and older versions left in the standard grid
GRID_AUTO_FIELDS = ("id", "left", "top", "right", "bottom", "row_index", "col_index")


def renumbered_cells(layer, crs, field_geom=None, field_engine=None):
    """
    Memory copy of the grid cells with a single integer field 'id' numbered 1, 2, 3...
    in the order of the cells; the columns created automatically by the grid tool
    (left, top, right, bottom and its own id) are dropped.

    With the field geometry, cells that only touch the boundary along an edge or a corner
    (no area inside the field) are dropped too: the final clip would remove them and leave
    gaps in the numbering.
    """
    out = QgsVectorLayer(f"Polygon?crs={crs.authid()}", "cells", "memory")
    out.dataProvider().addAttributes([QgsField(GRID_ID_FIELD, FIELD_INT)])
    out.updateFields()
    feats = []
    n = 0
    for f in layer.getFeatures():
        geom = f.geometry()
        if field_geom is not None and not (
                field_engine is not None and field_engine.contains(geom.constGet())):
            inter = field_geom.intersection(geom)
            if inter is None or inter.isEmpty() or inter.area() <= 1e-9 * max(geom.area(), 1.0):
                continue
        n += 1
        g = QgsFeature(out.fields())
        g.setGeometry(geom)
        g.setAttributes([n])
        feats.append(g)
    out.dataProvider().addFeatures(feats)
    out.updateExtents()
    return out


def previous_columns(path, ids, new_names):
    """
    Columns of an existing standard grid at ``path`` that must be kept in the new one:
    every column except the ID, the automatic grid columns and the attributes computed
    again now (``new_names``, which are replaced). Values are matched by ID, so the old
    file must hold exactly the same IDs (same boundary and cell size).

    Returns (fields, {id: [values]}) or None when there is nothing to keep, and the
    string 'mismatch' when the old file does not fit the new grid.
    """
    if not path or not os.path.exists(path):
        return None
    old = QgsVectorLayer(path, "old", "ogr")
    if not old.isValid() or old.fields().indexOf(GRID_ID_FIELD) < 0:
        return "mismatch"
    keep = [f for f in old.fields()
            if f.name().lower() not in GRID_AUTO_FIELDS
            and f.name().lower() not in {n.lower() for n in new_names}]
    old_ids = set()
    values = {}
    for f in old.getFeatures():
        fid = f[GRID_ID_FIELD]
        old_ids.add(fid)
        values[fid] = [f[k.name()] for k in keep]
    if old_ids != set(ids):
        return "mismatch"
    if not keep:
        return None
    fields = QgsFields()
    for k in keep:
        fields.append(QgsField(k))
    return fields, values


def write_standard_grid(layer, path, kept=None):
    """
    Write ``layer`` (clipped cells with ID and the new means) to the Shapefile ``path``,
    adding the columns kept from the previous file (``kept`` from previous_columns).
    The old file is replaced.
    """
    fields = QgsFields(layer.fields())
    extra = []
    if kept:
        extra_fields, values = kept
        for f in extra_fields:
            fields.append(QgsField(f))
            extra.append(f.name())
    mem = QgsVectorLayer(f"MultiPolygon?crs={layer.crs().authid()}", "out", "memory")
    mem.dataProvider().addAttributes(list(fields))
    mem.updateFields()
    feats = []
    for f in layer.getFeatures():
        g = QgsFeature(mem.fields())
        geom = QgsGeometry(f.geometry())
        if not geom.isMultipart():
            geom.convertToMultiType()
        g.setGeometry(geom)
        attrs = list(f.attributes())
        if extra:
            attrs += values.get(f[GRID_ID_FIELD], [None] * len(extra))
        g.setAttributes(attrs)
        feats.append(g)
    mem.dataProvider().addFeatures(feats)
    if os.path.exists(path) and not QgsVectorFileWriter.deleteShapeFile(path):
        raise QgsProcessingException(tr("err_grid_locked", path=os.path.basename(path)))
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "ESRI Shapefile"
    opts.fileEncoding = "UTF-8"
    res = QgsVectorFileWriter.writeAsVectorFormatV3(mem, path, QgsCoordinateTransformContext(),
                                                    opts)
    if res[0] != WRITER_NO_ERROR:
        raise QgsProcessingException(tr("err_create_file", path=path) + f"\n{res[1]}")
    return extra


class IdwJob:
    """
    Everything the workflow needs.

    boundary_input : value accepted by processing.run as INPUT (layer,
                     layer id or QgsProcessingFeatureSourceDefinition)
    boundary_extent: QgsRectangle of the boundary features (boundary CRS)
    boundary_crs   : QgsCoordinateReferenceSystem (projected, metres)
    items          : list of (point_source, field_name)
    output_path    : path of the standard grid with the means (.shp); when it already
                     exists, its other columns are kept and the new ones added/replaced
    raster_folder  : folder for the interpolated GeoTIFFs
    stamp          : text added to raster file names (avoids overwriting)
    params         : optional list of (power, radius) or (power, radius, max_neighbours),
                     one per item; each attribute has its own spatial dependence, so each
                     may have its own IDW parameters. When omitted, ``power``, ``radius``
                     and ``max_neighbours`` are used for every item.
    min_neighbours : every pixel uses at least this many samples (beyond the radius if needed)
    max_neighbours : and at most this many (the nearest ones); 0 = no maximum
    cell_size      : side of the vector grid cells (default: pixel size)
    grid_input     : existing polygon grid to use instead of generating one (only the
                     cells touching the boundary are used)
    grid_path      : ignored (kept for compatibility: the standard grid is the output)
    reuse_grid     : ignored (the grid is generated again, identical, at every run)
    """

    def __init__(self, boundary_input, boundary_extent, boundary_crs, items,
                 tolerance, power, radius, pixel, raster_folder, output_path, stamp="",
                 params=None, cell_size=None, grid_input=None, grid_path=None,
                 reuse_grid=False, min_neighbours=MIN_NEIGHBOURS,
                 max_neighbours=DEFAULT_MAX_NEIGHBOURS):
        self.boundary_input = boundary_input
        self.boundary_extent = boundary_extent
        self.boundary_crs = boundary_crs
        self.items = items
        self.tolerance = float(tolerance)
        self.power = float(power)
        self.radius = float(radius)
        self.pixel = float(pixel)
        self.raster_folder = raster_folder
        self.output_path = output_path
        self.stamp = stamp
        self.min_neighbours = int(min_neighbours)
        self.max_neighbours = int(max_neighbours)
        if params is None:
            params = [(self.power, self.radius)] * len(items)
        if len(params) != len(items):
            raise ValueError("params must have one (power, radius) per item")
        self.params = [(float(t[0]), float(t[1]),
                        int(t[2]) if len(t) > 2 and t[2] is not None else self.max_neighbours)
                       for t in params]
        self.cell_size = float(cell_size) if cell_size else self.pixel
        self.grid_input = grid_input
        self.grid_path = grid_path
        self.reuse_grid = bool(reuse_grid)

    def grid(self):
        """Raster grid: boundary extent plus RASTER_MARGIN, snapped to the pixel size."""
        e = buffered(self.boundary_extent, RASTER_MARGIN)
        return snap_extent(e.xMinimum(), e.yMinimum(), e.xMaximum(), e.yMaximum(), self.pixel)

    def cell_grid(self):
        """Vector grid extent: boundary extent snapped outward to the cell size."""
        e = self.boundary_extent
        return snap_extent(e.xMinimum(), e.yMinimum(), e.xMaximum(), e.yMaximum(), self.cell_size)


def fallback_share_in_field(used_fallback, xmin, ymax, res, field_geom, field_engine):
    """
    Percentage of the field area whose pixels had fewer samples within the search radius
    than the minimum of neighbours and therefore used the nearest samples beyond it. Pixels of the 100 m margin do not count.
    """
    import numpy as np
    rows, cols = np.nonzero(used_fallback)
    if rows.size == 0 or field_geom is None or field_engine is None:
        return 0.0
    area = field_geom.area()
    if area <= 0:
        return 0.0
    bb = field_geom.boundingBox()
    inside = 0
    for r, c in zip(rows, cols):
        x = xmin + (c + 0.5) * res
        y = ymax - (r + 0.5) * res
        if not (bb.xMinimum() <= x <= bb.xMaximum() and bb.yMinimum() <= y <= bb.yMaximum()):
            continue
        pt = QgsGeometry.fromPointXY(QgsPointXY(x, y))   # keep a reference while GEOS uses it
        if field_engine.intersects(pt.constGet()):
            inside += 1
    return min(100.0, inside * res * res / area * 100.0)


def _run(alg, params, context, feedback):
    return processing.run(alg, params, context=context, feedback=feedback,
                          is_child_algorithm=True)["OUTPUT"]


def run_idw_job(job, context, feedback):
    """
    Run the workflow. Returns a dict:
      output    -> path of the standard grid (clipped cells, ID and one column per attribute)
      kept      -> names of the columns kept from a previous run
      layers    -> list of dicts {prefix, field, label, mean_field, raster, n, power, radius}
      warnings  -> list of messages
    Raises QgsProcessingException on error or cancellation.

    Order (avoids cells without value along the border):
      1. IDW rasters over the boundary extent + 100 m, never masked or clipped;
      2. grid cells touching the boundary, kept WHOLE; a generated grid keeps only an
         ID numbered 1, 2, 3... (automatic columns of the grid tool removed);
      3. zonal mean of every raster in the whole cells;
      4. only then the cells are clipped by the boundary.
    """
    crs = job.boundary_crs
    res = job.pixel
    xmin, ymin, xmax, ymax, ncol, nrow = job.grid()
    search_rect = buffered(job.boundary_extent, job.tolerance)
    tctx = context.transformContext()

    n_items = len(job.items)
    steps = QgsProcessingMultiStepFeedback(2 * n_items + 5, feedback)
    step = 0

    prefixes = unique_prefixes([(name_of(s), f) for s, f in job.items])
    layers, warnings = [], []

    # boundary with fixed geometries (also used to tell which pixels are inside the field)
    steps.setCurrentStep(step)
    step += 1
    feedback.pushInfo(tr("log_fixing"))
    fixed = _run("native:fixgeometries", {"INPUT": job.boundary_input, "OUTPUT": "TEMPORARY_OUTPUT"},
                 context, steps)
    fixed_layer = QgsProcessingUtils.mapLayerFromString(fixed, context)
    field_geom = boundary_geometry(fixed_layer.getFeatures()) if fixed_layer is not None else None
    field_engine = None
    if field_geom is not None:
        field_engine = QgsGeometry.createGeometryEngine(field_geom.constGet())
        field_engine.prepareGeometry()

    # 1) IDW for each field, over the boundary extent plus a safety margin
    for (source, field), prefix, (power, radius, max_n) in zip(job.items, prefixes, job.params):
        steps.setCurrentStep(step)
        step += 1
        label = f"{field} ({name_of(source)})"
        feedback.pushInfo(tr("log_interpolating", label=label))
        xs, ys, zs = extract_points(source, field, search_rect, crs, tctx)
        if not zs:
            warnings.append(tr("warn_no_values", label=label))
            feedback.reportError(warnings[-1], fatalError=False)
            continue

        def cb(frac):
            steps.setProgress(frac * 100.0)
            return not feedback.isCanceled()

        feedback.pushInfo(tr("log_params", label=label, p=f"{power:g}",
                             r=tr("no_limit") if radius == 0 else f"{radius:.1f} m",
                             kmin=job.min_neighbours,
                             kmax=max_n if max_n else tr("no_limit")))
        result = idw_grid(xs, ys, zs, xmin, ymax, ncol, nrow, res, power, radius, cb,
                          min_neighbours=job.min_neighbours, max_neighbours=max_n,
                          return_fallback=True)
        if result is None or feedback.isCanceled():
            raise QgsProcessingException(tr("canceled"))
        grid, used_fallback = result
        fallback_pct = fallback_share_in_field(used_fallback, xmin, ymax, res, field_geom, field_engine)
        if fallback_pct > 0:
            warnings.append(tr("warn_fallback", label=label, pct=fmt(fallback_pct, 1),
                               k=job.min_neighbours))
            feedback.pushInfo(warnings[-1])
        raster = os.path.join(
            job.raster_folder,
            f"IDW_{safe_name(name_of(source), 25)}_{safe_name(field, 25)}{job.stamp}.tif")
        write_geotiff(raster, grid, xmin, ymax, res, crs)
        layers.append({"prefix": prefix, "field": field, "label": label,
                       "raster": raster, "n": len(zs), "power": power, "radius": radius,
                       "max_neighbours": max_n, "min_neighbours": job.min_neighbours,
                       "fallback_pct": fallback_pct})

    if not layers:
        raise QgsProcessingException(tr("err_nothing_interpolated") + "\n" + "\n".join(warnings))

    # 2) The vector grid: whole cells touching the boundary
    steps.setCurrentStep(step)
    step += 1
    generated = job.grid_input is None
    if not generated:
        feedback.pushInfo(tr("log_grid_existing"))
        grid_src = job.grid_input
        src_layer = QgsProcessingUtils.mapLayerFromString(grid_src, context) if isinstance(grid_src, str) else grid_src
        if src_layer is not None and hasattr(src_layer, "crs") and src_layer.crs() != crs:
            grid_src = _run("native:reprojectlayer", {"INPUT": grid_src, "TARGET_CRS": crs,
                                                     "OUTPUT": "TEMPORARY_OUTPUT"}, context, steps)
    else:
        feedback.pushInfo(tr("log_grid"))
        gx0, gy0, gx1, gy1, _, _ = job.cell_grid()
        grid_src = _run("native:creategrid", {
            "TYPE": 2, "EXTENT": f"{gx0},{gx1},{gy0},{gy1} [{crs.authid()}]",
            "HSPACING": job.cell_size, "VSPACING": job.cell_size, "HOVERLAY": 0, "VOVERLAY": 0,
            "CRS": crs, "OUTPUT": "TEMPORARY_OUTPUT"}, context, steps)

    steps.setCurrentStep(step)
    step += 1
    cells = _run("native:extractbylocation", {
        "INPUT": grid_src, "PREDICATE": [0], "INTERSECT": fixed,   # 0 = intersects
        "OUTPUT": "TEMPORARY_OUTPUT"}, context, steps)
    cells_layer = QgsProcessingUtils.mapLayerFromString(cells, context)
    if cells_layer is None:
        cells_layer = QgsVectorLayer(cells, "cells", "ogr")
    if cells_layer is None or not cells_layer.isValid() or cells_layer.featureCount() == 0:
        raise QgsProcessingException(tr("err_empty_grid"))
    if generated:
        # only the ID, renumbered 1, 2, 3... before the zonal statistics
        cells_layer = renumbered_cells(cells_layer, crs, field_geom, field_engine)
        cells = cells_layer
        feedback.pushInfo(tr("log_grid_ids", n=cells_layer.featureCount()))

    # final column names: the attribute names (Shapefile: at most 10 characters)
    existing = [f.name() for f in cells_layer.fields()]
    names = shapefile_field_names([info["field"] for info in layers], existing)
    for info, name in zip(layers, names):
        info["mean_field"] = name

    # 3) Zonal statistics (mean) in the WHOLE cells, chained in one layer
    current = cells
    for i, info in enumerate(layers):
        if feedback.isCanceled():
            raise QgsProcessingException(tr("canceled"))
        steps.setCurrentStep(step)
        step += 1
        feedback.pushInfo(tr("log_zonal", label=info["label"]))
        current = _run("native:zonalstatisticsfb", {
            "INPUT": current, "INPUT_RASTER": info["raster"], "RASTER_BAND": 1,
            "COLUMN_PREFIX": f"z{i}_", "STATISTICS": [2],  # 2 = mean
            "OUTPUT": "TEMPORARY_OUTPUT"}, context, steps)

    # rename z<i>_mean to the attribute names
    steps.setCurrentStep(step)
    step += 1
    stats_layer = QgsProcessingUtils.mapLayerFromString(current, context)
    rename = {f"z{i}_mean": info["mean_field"] for i, info in enumerate(layers)}
    mapping = []
    for f in stats_layer.fields():
        mapping.append({"expression": f'"{f.name()}"', "name": rename.get(f.name(), f.name()),
                        "type": f.type(), "length": f.length(), "precision": f.precision()})
    current = _run("native:refactorfields", {"INPUT": current, "FIELDS_MAPPING": mapping,
                                             "OUTPUT": "TEMPORARY_OUTPUT"}, context, steps)

    # 4) Only now clip the cells by the boundary (values already computed on whole cells)
    steps.setCurrentStep(step)
    feedback.pushInfo(tr("log_clip"))
    clipped = _run("native:clip", {"INPUT": current, "OVERLAY": fixed,
                                   "OUTPUT": "TEMPORARY_OUTPUT"}, context, steps)
    clipped_layer = QgsProcessingUtils.mapLayerFromString(clipped, context)

    # 5) Single output: the standard grid. Columns of a previous run are kept (matched by
    #    ID); the attributes computed now are added or replaced.
    kept = None
    if clipped_layer.fields().indexOf(GRID_ID_FIELD) >= 0:
        ids = [f[GRID_ID_FIELD] for f in clipped_layer.getFeatures()]
        kept = previous_columns(job.output_path, ids, [i["mean_field"] for i in layers])
        if kept == "mismatch":
            warnings.append(tr("warn_grid_replaced", name=os.path.basename(job.output_path)))
            kept = None
    elif os.path.exists(job.output_path):
        warnings.append(tr("warn_grid_replaced", name=os.path.basename(job.output_path)))
    kept_names = write_standard_grid(clipped_layer, job.output_path, kept)
    if kept_names:
        feedback.pushInfo(tr("log_grid_kept", cols=", ".join(kept_names)))
    feedback.pushInfo(tr("log_grid_saved", path=os.path.basename(job.output_path)))

    steps.setCurrentStep(2 * n_items + 5)
    return {"output": job.output_path, "kept": kept_names, "layers": layers,
            "warnings": warnings}
