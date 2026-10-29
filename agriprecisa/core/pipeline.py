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
    QgsCoordinateTransform, QgsFeatureRequest, QgsGeometry, QgsRectangle,
    QgsProcessingException, QgsProcessingMultiStepFeedback, QgsProcessingUtils,
    QgsGraduatedSymbolRenderer, QgsClassificationJenks, QgsStyle, QgsFillSymbol,
)

from .compat import UNIT_METERS
from .idw_math import NODATA, idw_grid, safe_name, snap_extent, unique_prefixes
from ..i18n import tr

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
class IdwJob:
    """
    Everything the workflow needs.

    boundary_input : value accepted by processing.run as INPUT (layer,
                     layer id or QgsProcessingFeatureSourceDefinition)
    boundary_extent: QgsRectangle of the boundary features (boundary CRS)
    boundary_crs   : QgsCoordinateReferenceSystem (projected, metres)
    items          : list of (point_source, field_name)
    output_path    : .gpkg path for the final polygon grid
    raster_folder  : folder for the interpolated GeoTIFFs
    stamp          : text added to raster file names (avoids overwriting)
    """

    def __init__(self, boundary_input, boundary_extent, boundary_crs, items,
                 tolerance, power, radius, pixel, raster_folder, output_path, stamp=""):
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

    def grid(self):
        e = self.boundary_extent
        return snap_extent(e.xMinimum(), e.yMinimum(), e.xMaximum(), e.yMaximum(), self.pixel)


def run_idw_job(job, context, feedback):
    """
    Run the workflow. Returns a dict:
      output   -> path of the final GeoPackage
      layers   -> list of dicts {prefix, field, label, mean_field, raster, n}
      warnings -> list of messages
    Raises QgsProcessingException on error or cancellation.
    """
    crs = job.boundary_crs
    res = job.pixel
    xmin, ymin, xmax, ymax, ncol, nrow = job.grid()
    search_rect = buffered(job.boundary_extent, job.tolerance)
    tctx = context.transformContext()

    n_items = len(job.items)
    steps = QgsProcessingMultiStepFeedback(2 * n_items + 3, feedback)
    step = 0

    prefixes = unique_prefixes([(name_of(s), f) for s, f in job.items])
    layers, warnings = [], []

    # 1) IDW for each field
    for (source, field), prefix in zip(job.items, prefixes):
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

        grid = idw_grid(xs, ys, zs, xmin, ymax, ncol, nrow, res, job.power, job.radius, cb)
        if grid is None or feedback.isCanceled():
            raise QgsProcessingException(tr("canceled"))
        raster = os.path.join(
            job.raster_folder,
            f"IDW_{safe_name(name_of(source), 25)}_{safe_name(field, 25)}{job.stamp}.tif")
        write_geotiff(raster, grid, xmin, ymax, res, crs)
        layers.append({"prefix": prefix, "field": field, "label": label,
                       "mean_field": prefix + "_mean", "raster": raster, "n": len(zs)})

    if not layers:
        raise QgsProcessingException(tr("err_nothing_interpolated") + "\n" + "\n".join(warnings))

    # 2) Polygon grid with the pixel size, clipped by the boundary
    steps.setCurrentStep(step)
    step += 1
    feedback.pushInfo(tr("log_fixing"))
    fixed = processing.run("native:fixgeometries", {
        "INPUT": job.boundary_input, "OUTPUT": "TEMPORARY_OUTPUT"},
        context=context, feedback=steps, is_child_algorithm=True)["OUTPUT"]

    steps.setCurrentStep(step)
    step += 1
    feedback.pushInfo(tr("log_grid"))
    grid_layer = processing.run("native:creategrid", {
        "TYPE": 2,
        "EXTENT": f"{xmin},{xmax},{ymin},{ymax} [{crs.authid()}]",
        "HSPACING": res, "VSPACING": res, "HOVERLAY": 0, "VOVERLAY": 0,
        "CRS": crs, "OUTPUT": "TEMPORARY_OUTPUT"},
        context=context, feedback=steps, is_child_algorithm=True)["OUTPUT"]

    steps.setCurrentStep(step)
    step += 1
    feedback.pushInfo(tr("log_clip"))
    clipped = processing.run("native:clip", {
        "INPUT": grid_layer, "OVERLAY": fixed, "OUTPUT": "TEMPORARY_OUTPUT"},
        context=context, feedback=steps, is_child_algorithm=True)["OUTPUT"]
    clipped_layer = QgsProcessingUtils.mapLayerFromString(clipped, context)
    if clipped_layer is None or clipped_layer.featureCount() == 0:
        raise QgsProcessingException(tr("err_empty_grid"))

    # 3) Zonal statistics (mean), chained so every column ends up in one layer
    current = clipped
    for i, info in enumerate(layers):
        if feedback.isCanceled():
            raise QgsProcessingException(tr("canceled"))
        steps.setCurrentStep(step)
        step += 1
        feedback.pushInfo(tr("log_zonal", label=info["label"]))
        last = i == len(layers) - 1
        current = processing.run("native:zonalstatisticsfb", {
            "INPUT": current, "INPUT_RASTER": info["raster"], "RASTER_BAND": 1,
            "COLUMN_PREFIX": info["prefix"] + "_", "STATISTICS": [2],  # 2 = mean
            "OUTPUT": job.output_path if last else "TEMPORARY_OUTPUT"},
            context=context, feedback=steps, is_child_algorithm=True)["OUTPUT"]

    steps.setCurrentStep(2 * n_items + 3)
    return {"output": job.output_path, "layers": layers, "warnings": warnings}
