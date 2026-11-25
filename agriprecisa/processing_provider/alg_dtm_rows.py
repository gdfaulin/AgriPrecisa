# -*- coding: utf-8 -*-
"""AgriPrecisa: Processing algorithm 'DTM and plant height in row crops (from the DSM)'."""

import os

import numpy as np
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingException, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterFeatureSink, QgsProcessingOutputLayerDefinition, QgsProperty,
    QgsFields, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsFeatureSink,
    QgsMarkerSymbol, QgsFillSymbol, QgsGraduatedSymbolRenderer, QgsClassificationJenks,
    QgsProcessingParameterNumber, QgsProcessingParameterBoolean, QgsProcessingParameterEnum,
    QgsProcessingParameterRasterDestination, QgsProcessingLayerPostProcessorInterface,
    QgsProject, QgsStyle, QgsColorRampShader, QgsRasterShader,
    QgsSingleBandPseudoColorRenderer, QgsPalettedRasterRenderer,
)

from ..core.compat import (NUMBER_DOUBLE, SHADER_LINEAR, SRC_POLYGON, SRC_POINT, FIELD_INT,
                           FIELD_DOUBLE, WKB_POINT, WKB_POLYGON, WKB_MULTIPOLYGON)
from ..core import mdt_math as mm
from ..core import mdt_stats as ms
from ..core.paths import free_output_path
from ..i18n import tr, fmt

ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icons", "mdt.png")
HELP_URL = "https://github.com/gdfaulin/AgriPrecisa#readme"
NODATA = -9999.0
MASK_NODATA = 255


CROP_KEYS = {
    "coffee": "mdt_crop_coffee", "citrus": "mdt_crop_citrus", "maize": "mdt_crop_maize",
    "soybean": "mdt_crop_soybean", "sugarcane": "mdt_crop_sugarcane",
    "grapevine": "mdt_crop_grapevine", "eucalyptus": "mdt_crop_eucalyptus",
    "custom": "mdt_crop_custom",
}


def crop_name(index):
    return tr(CROP_KEYS[mm.CROPS[index][0]])


# ---------------------------------------------------------------- styles
def style_pseudocolor(layer, vmin, vmax, ramp_name, invert=False):
    """Continuous colour ramp between vmin and vmax with 5 labelled stops."""
    if layer is None or not layer.isValid() or vmin is None or vmax is None:
        return
    if vmax <= vmin:
        vmax = vmin + 1.0
    ramp = QgsStyle.defaultStyle().colorRamp(ramp_name)
    if ramp is None:
        return
    if invert:
        ramp.invert()
    shader = QgsColorRampShader(vmin, vmax)
    shader.setColorRampType(SHADER_LINEAR)
    shader.setSourceColorRamp(ramp.clone())
    items = []
    for i in range(5):
        value = vmin + (vmax - vmin) * i / 4.0
        items.append(QgsColorRampShader.ColorRampItem(value, ramp.color(i / 4.0), fmt(value, 2)))
    shader.setColorRampItemList(items)
    raster_shader = QgsRasterShader()
    raster_shader.setRasterShaderFunction(shader)
    renderer = QgsSingleBandPseudoColorRenderer(layer.dataProvider(), 1, raster_shader)
    renderer.setClassificationMin(vmin)
    renderer.setClassificationMax(vmax)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def style_plant_mask(layer):
    """1 = plant (green), 0 = soil (brown)."""
    if layer is None or not layer.isValid():
        return
    classes = [QgsPalettedRasterRenderer.Class(1, QColor("#2e7d32"), tr("mdt_class_plants")),
               QgsPalettedRasterRenderer.Class(0, QColor("#a1785c"), tr("mdt_class_soil"))]
    layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes))
    layer.triggerRepaint()


def style_graduated_vector(layer, field, kind):
    """Graduated style (5 classes, Jenks, Viridis) for row segments, plant tops or crowns."""
    if layer is None or not layer.isValid() or layer.fields().indexOf(field) < 0:
        return
    if kind == "points":
        symbol = QgsMarkerSymbol.createSimple({"name": "circle", "size": "2.2",
                                              "outline_color": "#202020", "outline_width": "0.2"})
    elif kind == "crowns":
        symbol = QgsFillSymbol.createSimple({"outline_color": "#202020", "outline_width": "0.1"})
    else:
        symbol = QgsFillSymbol.createSimple({"outline_style": "no"})
    renderer = QgsGraduatedSymbolRenderer(field)
    renderer.setSourceSymbol(symbol)
    ramp = QgsStyle.defaultStyle().colorRamp("Viridis")
    if ramp is not None:
        renderer.setSourceColorRamp(ramp)
    renderer.setClassificationMethod(QgsClassificationJenks())
    renderer.updateClasses(layer, 5)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


ROW_FIELDS = [("linha", FIELD_INT), ("trecho", FIELD_INT), ("alt_media", FIELD_DOUBLE),
              ("alt_p95", FIELD_DOUBLE), ("alt_max", FIELD_DOUBLE), ("cobert_pct", FIELD_DOUBLE),
              ("falha_m", FIELD_DOUBLE), ("compr_m", FIELD_DOUBLE)]
PLANT_FIELDS = [("id", FIELD_INT), ("alt_max", FIELD_DOUBLE), ("alt_media", FIELD_DOUBLE),
                ("area_m2", FIELD_DOUBLE), ("diam_m", FIELD_DOUBLE)]


def make_fields(spec):
    fields = QgsFields()
    for name, ftype in spec:
        fields.append(QgsField(name, ftype))
    return fields


def crown_geometries(crowns, gt, wkt):
    """{plant id: QgsGeometry} from the crown raster (GDAL Polygonize, parts collected)."""
    from osgeo import gdal, ogr, osr
    rows, cols = crowns.shape
    mem = gdal.GetDriverByName("MEM").Create("", cols, rows, 1, gdal.GDT_Int32)
    mem.SetGeoTransform(gt)
    mem.SetProjection(wkt)
    band = mem.GetRasterBand(1)
    band.WriteArray(crowns)
    srs = osr.SpatialReference()
    srs.ImportFromWkt(wkt)
    vds = ogr.GetDriverByName("Memory").CreateDataSource("crowns")
    vlayer = vds.CreateLayer("crowns", srs, ogr.wkbPolygon)
    vlayer.CreateField(ogr.FieldDefn("id", ogr.OFTInteger))
    gdal.Polygonize(band, band, vlayer, 0, [], callback=None)
    parts = {}
    for feat in vlayer:
        pid = feat.GetField(0)
        if pid:
            parts.setdefault(pid, []).append(QgsGeometry.fromWkt(feat.GetGeometryRef().ExportToWkt()))
    return {pid: (geoms[0] if len(geoms) == 1 else QgsGeometry.collectGeometry(geoms))
            for pid, geoms in parts.items()}


class _RasterStylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Applies the AgriPrecisa style when an output is loaded into the project."""

    alive = []  # keeps references until QGIS uses them

    def __init__(self, kind, vmin=None, vmax=None):
        super().__init__()
        self.kind, self.vmin, self.vmax = kind, vmin, vmax

    def postProcessLayer(self, layer, context, feedback):
        if self.kind == "dtm":
            style_pseudocolor(layer, self.vmin, self.vmax, "Spectral", invert=True)
        elif self.kind == "height":
            style_pseudocolor(layer, self.vmin, self.vmax, "Viridis")
        elif self.kind == "mask":
            style_plant_mask(layer)
        elif self.kind == "rows":
            style_graduated_vector(layer, "alt_media", "rows")
        elif self.kind == "plants":
            style_graduated_vector(layer, "alt_max", "points")
        elif self.kind == "crowns":
            style_graduated_vector(layer, "alt_max", "crowns")

    @classmethod
    def create(cls, kind, vmin=None, vmax=None):
        pp = cls(kind, vmin, vmax)
        cls.alive.append(pp)
        return pp


# ---------------------------------------------------------------- crop list -> fields
def _crop_wrapper_class():
    """
    Python widget wrapper for the crop list that fills spacing, resolution and tolerance with
    the values of the chosen crop (regression 2.0.1: the fields stayed at 0 and the student did
    not see the suggested values). Built on demand because processing.gui only exists in the
    QGIS desktop; returns None when it is not available (fields keep the 0 = crop value rule).
    """
    try:
        from processing.gui.wrappers import WidgetWrapper, DIALOG_STANDARD
        from qgis.PyQt.QtWidgets import QComboBox
    except ImportError:
        return None

    class CropWidgetWrapper(WidgetWrapper):
        def createWidget(self, **kwargs):
            self.combobox = QComboBox()
            for i, option in enumerate(self.parameterDefinition().options()):
                self.combobox.addItem(option, i)
            default = self.parameterDefinition().defaultValue()
            self.combobox.setCurrentIndex(int(default) if default is not None else 0)
            return self.combobox

        def setValue(self, value):
            index = self.combobox.findData(value)
            if index >= 0:
                self.combobox.setCurrentIndex(index)

        def value(self):
            return self.combobox.currentData()

        def postInitialize(self, wrappers):
            self._fields = {}
            if self.dialogType != DIALOG_STANDARD:
                return  # batch and modeler: fields keep the 0 = crop value rule
            for w in wrappers:
                name = w.parameterDefinition().name()
                if name in CROP_FIELDS:
                    self._fields[name] = w
            self.combobox.currentIndexChanged.connect(self.fill_fields)
            self.fill_fields()

        def fill_fields(self, *_args):
            for name, value in crop_field_values(self.combobox.currentData()).items():
                wrapper = self._fields.get(name)
                if wrapper is not None:
                    set_wrapper_value(wrapper, value)

    return CropWidgetWrapper


CROP_FIELDS = mm.CROP_FIELDS
crop_field_values = mm.crop_field_values


def set_wrapper_value(wrapper, value):
    """Sets a value on a C++ (QgsAbstractProcessingParameterWidgetWrapper) or Python wrapper."""
    if hasattr(wrapper, "setParameterValue"):
        from qgis.core import QgsProcessingContext
        wrapper.setParameterValue(value, QgsProcessingContext())
    else:
        wrapper.setValue(value)


# ---------------------------------------------------------------- algorithm
class DtmRowCropsAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    CROP = "CROP"
    SPACING = "SPACING"
    FACTOR = "FACTOR"
    RESOLUTION = "RESOLUTION"
    TOLERANCE = "TOLERANCE"
    ZERO_NODATA = "ZERO_NODATA"
    OUT_DTM = "OUT_DTM"
    OUT_HEIGHT = "OUT_HEIGHT"
    OUT_MASK = "OUT_MASK"
    SEGMENT = "SEGMENT"
    PLANT_DISTANCE = "PLANT_DISTANCE"
    OUT_ROWS = "OUT_ROWS"
    OUT_PLANTS = "OUT_PLANTS"
    OUT_CROWNS = "OUT_CROWNS"

    def createInstance(self):
        return DtmRowCropsAlgorithm()

    def name(self):
        return "dtm_row_crops"

    def displayName(self):
        return tr("mdt_alg_name")

    def group(self):
        return tr("mdt_alg_group")

    def groupId(self):
        return "elevation"

    def icon(self):
        return QIcon(ICON)

    def tags(self):
        return tr("mdt_tags").split(",")

    def shortHelpString(self):
        return tr("mdt_help")

    def helpUrl(self):
        return HELP_URL

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterRasterLayer(self.INPUT, tr("mdt_p_input")))
        crops = [crop_name(i) for i in range(len(mm.CROPS))]
        crop_param = QgsProcessingParameterEnum(
            self.CROP, tr("mdt_p_crop"), options=crops, defaultValue=0)
        wrapper_class = _crop_wrapper_class()
        if wrapper_class is not None:
            crop_param.setMetadata({"widget_wrapper": {"class": wrapper_class}})
        self.addParameter(crop_param)
        self.addParameter(QgsProcessingParameterNumber(
            self.SPACING, tr("mdt_p_spacing"), NUMBER_DOUBLE, 0.0, minValue=0.0, maxValue=20.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.FACTOR, tr("mdt_p_factor"), NUMBER_DOUBLE, mm.DEFAULT_FACTOR,
            minValue=1.0, maxValue=4.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.RESOLUTION, tr("mdt_p_resolution"), NUMBER_DOUBLE, 0.0, minValue=0.0, maxValue=5.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.TOLERANCE, tr("mdt_p_tolerance"), NUMBER_DOUBLE, 0.0, minValue=0.0, maxValue=2.0))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ZERO_NODATA, tr("mdt_p_zero"), defaultValue=True))

        # default: project folder, when the project has been saved
        home = QgsProject.instance().homePath()

        def default(name):
            return os.path.join(home, name) if home else None

        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_DTM, tr("mdt_p_out_dtm"), defaultValue=default("MDT.tif")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_HEIGHT, tr("mdt_p_out_height"), defaultValue=default("Altura_plantas.tif")))
        self.addParameter(QgsProcessingParameterRasterDestination(
            self.OUT_MASK, tr("mdt_p_out_mask"), defaultValue=default("Mascara_planta.tif"),
            optional=True, createByDefault=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.SEGMENT, tr("mdt_p_segment"), NUMBER_DOUBLE, ms.DEFAULT_SEGMENT,
            minValue=0.5, maxValue=500.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.PLANT_DISTANCE, tr("mdt_p_plant_distance"), NUMBER_DOUBLE, 0.0,
            minValue=0.0, maxValue=20.0))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUT_ROWS, tr("mdt_p_out_rows"), SRC_POLYGON,
            defaultValue=default("Altura_trechos_linhas.shp"), optional=True, createByDefault=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUT_PLANTS, tr("mdt_p_out_plants"), SRC_POINT,
            defaultValue=default("Altura_plantas_topos.shp"), optional=True, createByDefault=False))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUT_CROWNS, tr("mdt_p_out_crowns"), SRC_POLYGON,
            defaultValue=default("Altura_plantas_copas.shp"), optional=True, createByDefault=False))

    # ------------------------------------------------------------ helpers
    @staticmethod
    def _unlocked_output(path, label, context, feedback):
        """Regression 2.0.0: an output already loaded in QGIS (Windows) could not be replaced
        and the run failed at the very end. Use a free name instead and keep it loadable."""
        if not path:
            return path
        free = free_output_path(path)
        if free == path:
            return path
        feedback.reportError(tr("mdt_warn_locked", label=label, old=os.path.basename(path),
                                new=os.path.basename(free)), fatalError=False)
        layers = context.layersToLoadOnCompletion()
        if path in layers:
            details = layers.pop(path)
            context.setLayersToLoadOnCompletion(layers)
            context.addLayerToLoadOnCompletion(free, details)
        return free

    def _sink(self, parameters, name, context, fields, wkb, crs, label, feedback):
        """Feature sink, redirected to a free name when the file is open in QGIS (Windows)."""
        value = parameters.get(name)
        if value is None:
            return None, None
        params = dict(parameters)
        target = value.sink.staticValue() if isinstance(value, QgsProcessingOutputLayerDefinition) else value
        if isinstance(target, str) and target and not target.startswith(("memory:", "ogr:", "postgres")):
            free = free_output_path(target)
            if free != target:
                feedback.reportError(tr("mdt_warn_locked", label=label, old=os.path.basename(target),
                                        new=os.path.basename(free)), fatalError=False)
                if isinstance(value, QgsProcessingOutputLayerDefinition):
                    new = QgsProcessingOutputLayerDefinition(value)
                    new.sink = QgsProperty.fromValue(free)
                    params[name] = new
                else:
                    params[name] = free
        return self.parameterAsSink(params, name, context, fields, wkb, crs)

    @staticmethod
    def _save(array, path, gt, proj, dtype, nodata):
        from osgeo import gdal
        driver = gdal.GetDriverByName("GTiff")
        rows, cols = array.shape
        out = driver.Create(path, cols, rows, 1, dtype, options=["COMPRESS=LZW", "TILED=YES"])
        if out is None:
            raise QgsProcessingException(tr("mdt_err_write", path=path))
        out.SetGeoTransform(gt)
        out.SetProjection(proj)
        band = out.GetRasterBand(1)
        band.SetNoDataValue(nodata)
        band.WriteArray(array)
        band.FlushCache()
        out = None

    @staticmethod
    def _style_on_load(context, path, post_processor):
        if path and context.willLoadLayerOnCompletion(path):
            context.layerToLoadOnCompletionDetails(path).setPostProcessor(post_processor)

    # ------------------------------------------------------------ run
    def processAlgorithm(self, parameters, context, feedback):
        import importlib.util
        if importlib.util.find_spec("scipy") is None:  # clear message instead of a traceback
            raise QgsProcessingException(tr("mdt_err_scipy"))
        from osgeo import gdal

        _RasterStylePostProcessor.alive = []
        layer = self.parameterAsRasterLayer(parameters, self.INPUT, context)
        if layer is None:
            raise QgsProcessingException(tr("mdt_err_input"))
        if layer.crs().isGeographic():
            raise QgsProcessingException(tr("mdt_err_geographic", crs=layer.crs().authid()))

        crop = self.parameterAsEnum(parameters, self.CROP, context)
        spacing, resol, tol = mm.resolve_parameters(
            crop,
            self.parameterAsDouble(parameters, self.SPACING, context),
            self.parameterAsDouble(parameters, self.RESOLUTION, context),
            self.parameterAsDouble(parameters, self.TOLERANCE, context))
        if not spacing:
            raise QgsProcessingException(tr("mdt_err_custom_spacing"))
        factor = self.parameterAsDouble(parameters, self.FACTOR, context)
        zero_nd = self.parameterAsBoolean(parameters, self.ZERO_NODATA, context)
        feedback.pushInfo(tr("mdt_log_params", crop=crop_name(crop),
                             spacing=fmt(spacing, 2), res=fmt(resol, 2), tol=fmt(tol, 2),
                             factor=fmt(factor, 1)))
        rec = mm.recommended_resolution(spacing)
        if resol > rec:
            feedback.reportError(tr("mdt_warn_resolution", res=fmt(resol, 2), spacing=fmt(spacing, 2),
                                    rec=fmt(rec, 2)), fatalError=False)

        out_dtm = self._unlocked_output(self.parameterAsOutputLayer(parameters, self.OUT_DTM, context),
                                        tr("mdt_p_out_dtm"), context, feedback)
        out_height = self._unlocked_output(
            self.parameterAsOutputLayer(parameters, self.OUT_HEIGHT, context),
            tr("mdt_p_out_height"), context, feedback)
        out_mask = self._unlocked_output(
            self.parameterAsOutputLayer(parameters, self.OUT_MASK, context),
            tr("mdt_p_out_mask"), context, feedback)

        src = gdal.Open(layer.source())
        if src is None:
            raise QgsProcessingException(tr("mdt_err_open"))
        native = abs(src.GetGeoTransform()[1])
        if resol < native * 0.99:
            feedback.pushInfo(tr("mdt_log_finer", res=fmt(resol, 3), native=fmt(native, 3)))
        nd_src = src.GetRasterBand(1).GetNoDataValue()
        if nd_src is None and zero_nd:
            nd_src = 0

        # 1. resampling keeping the lowest point of each new pixel
        feedback.pushInfo(tr("mdt_step1"))
        ds = gdal.Warp("", src, format="MEM", xRes=resol, yRes=resol, resampleAlg="min",
                       srcNodata=nd_src, dstNodata=NODATA)
        dsm = ds.GetRasterBand(1).ReadAsArray().astype("float64")
        dsm[dsm == NODATA] = np.nan
        if zero_nd:
            dsm[dsm == 0] = np.nan
        valid = np.isfinite(dsm)
        if not valid.any():
            raise QgsProcessingException(tr("mdt_err_empty"))
        gt, proj = ds.GetGeoTransform(), ds.GetProjection()
        rows, cols = dsm.shape
        pixel = abs(gt[1])
        window = mm.window_pixels(spacing, factor, pixel)
        if window < mm.MIN_WINDOW:
            raise QgsProcessingException(tr("mdt_err_window", n=window, rec=fmt(rec, 2)))
        feedback.pushInfo(tr("mdt_log_window", pixel=fmt(pixel, 2), n=window,
                             size=fmt(window * pixel, 2)))
        feedback.setProgress(15)
        if feedback.isCanceled():
            return {}

        # 2. morphological opening
        feedback.pushInfo(tr("mdt_step2"))
        opening = mm.ground_surface(dsm, valid, window)
        feedback.setProgress(35)
        if feedback.isCanceled():
            return {}

        # 3. soil classification
        feedback.pushInfo(tr("mdt_step3"))
        soil = mm.classify_soil(dsm, opening, valid, tol)
        perc = mm.soil_percent(soil, valid)
        feedback.pushInfo(tr("mdt_log_soil", pct=fmt(perc, 1)))
        if perc < mm.LOW_SOIL_PERCENT:
            feedback.reportError(tr("mdt_warn_low_soil"), fatalError=False)
        elif perc > mm.HIGH_SOIL_PERCENT:
            feedback.reportError(tr("mdt_warn_high_soil"), fatalError=False)
        feedback.setProgress(45)

        # 4. terrain under the plants (GDAL FillNodata, inverse distance)
        feedback.pushInfo(tr("mdt_step4"))
        mem = gdal.GetDriverByName("MEM").Create("", cols, rows, 1, gdal.GDT_Float32)
        mem.SetGeoTransform(gt)
        mem.SetProjection(proj)
        band = mem.GetRasterBand(1)
        band.SetNoDataValue(NODATA)
        band.WriteArray(np.where(soil, dsm, NODATA).astype("float32"))
        gdal.FillNodata(targetBand=band, maskBand=None, maxSearchDist=window * 4,
                        smoothingIterations=0)
        filled = band.ReadAsArray().astype("float64")
        filled[filled == NODATA] = np.nan
        feedback.setProgress(70)
        if feedback.isCanceled():
            return {}

        # 5. smoothing
        feedback.pushInfo(tr("mdt_step5"))
        dtm = mm.smooth_dtm(filled, dsm, valid, window)
        height = dsm - dtm
        feedback.setProgress(85)

        # 6. saving
        feedback.pushInfo(tr("mdt_step6"))
        self._save(np.where(np.isnan(dtm), NODATA, dtm).astype("float32"), out_dtm, gt, proj,
                   gdal.GDT_Float32, NODATA)
        self._save(np.where(np.isnan(height), NODATA, height).astype("float32"), out_height, gt, proj,
                   gdal.GDT_Float32, NODATA)
        if out_mask:
            # plant mask: 1 = plant, 0 = soil (2.1.1; it was a soil mask with 1 = soil)
            mask = np.where(valid, (~soil).astype("uint8"), MASK_NODATA).astype("uint8")
            self._save(mask, out_mask, gt, proj, gdal.GDT_Byte, MASK_NODATA)
        feedback.setProgress(100)

        dmin, dmax = float(np.nanmin(dtm)), float(np.nanmax(dtm))
        feedback.pushInfo(tr("mdt_log_dtm_range", vmin=fmt(dmin, 2), vmax=fmt(dmax, 2)))
        stats = mm.height_stats(height, soil, valid)
        hmax = 1.0
        if stats is None:
            feedback.reportError(tr("mdt_log_no_plants"), fatalError=False)
        else:
            hmax = max(stats["p95"], 0.1)
            feedback.pushInfo(tr("mdt_log_height", mean=fmt(stats["mean"], 2),
                                 p95=fmt(stats["p95"], 2), max=fmt(stats["max"], 2),
                                 plants=fmt(stats["plant_percent"], 1)))

        crop_key = mm.CROPS[crop][0]
        plant_min = ms.plant_threshold(tol)
        distance = self.parameterAsDouble(parameters, self.PLANT_DISTANCE, context)
        if distance <= 0:
            distance = ms.plant_distance(crop_key, spacing)
        segment = self.parameterAsDouble(parameters, self.SEGMENT, context)
        crs = layer.crs()
        extra = {}

        # 7. row segments
        if parameters.get(self.OUT_ROWS) is not None:
            feedback.pushInfo(tr("mdt_step_rows"))
            plant_mask = valid & np.isfinite(height) & (height >= plant_min)
            theta, score = ms.row_direction(plant_mask, valid, gt, spacing)
            if score < 0.02:
                feedback.reportError(tr("mdt_warn_no_rows"), fatalError=False)
            else:
                s_found, phi = ms.row_comb(plant_mask, valid, gt, theta, spacing)
                azimuth = np.degrees(np.arctan2(-np.sin(theta), np.cos(theta))) % 180.0
                feedback.pushInfo(tr("mdt_log_rows_found", az=fmt(azimuth, 1), s=fmt(s_found, 2),
                                     informed=fmt(spacing, 2)))
                segs = ms.row_segments(height, valid, gt, theta, s_found, phi, segment, plant_min,
                                       ms.min_gap_length(distance, pixel))
                sink, dest = self._sink(parameters, self.OUT_ROWS, context, make_fields(ROW_FIELDS),
                                        WKB_POLYGON, crs, tr("mdt_p_out_rows"), feedback)
                if sink is not None:
                    for o in segs:
                        f = QgsFeature()
                        f.setGeometry(QgsGeometry.fromPolygonXY([[QgsPointXY(x, y) for x, y in o["corners"]]]))
                        f.setAttributes([o["row"], o["segment"], round(o["mean"], 3), round(o["p95"], 3),
                                         round(o["max"], 3), round(100 * o["coverage"], 1),
                                         round(o["gap"], 2), round(o["length"], 2)])
                        sink.addFeature(f, QgsFeatureSink.Flag.FastInsert)
                    extra[self.OUT_ROWS] = dest
                    self._style_on_load(context, dest, _RasterStylePostProcessor.create("rows"))
                total_len = sum(o["length"] for o in segs)
                total_gap = sum(o["gap"] for o in segs)
                feedback.pushInfo(tr(
                    "mdt_log_rows", rows=len({o["row"] for o in segs}), segs=len(segs),
                    cov=fmt(100 * np.mean([o["coverage"] for o in segs]) if segs else 0, 1),
                    gap=fmt(total_gap, 1), gap_pct=fmt(100 * total_gap / total_len if total_len else 0, 1),
                    min_gap=fmt(ms.min_gap_length(distance, pixel), 2)))
            if feedback.isCanceled():
                return {}

        # 8. plants (tops and crowns)
        if parameters.get(self.OUT_PLANTS) is not None or parameters.get(self.OUT_CROWNS) is not None:
            feedback.pushInfo(tr("mdt_step_plants", d=fmt(distance, 2)))
            plants, crowns = ms.detect_plants(height, valid, gt, distance, plant_min)
            area_ha = valid.sum() * pixel * pixel / 10000.0
            if plants:
                feedback.pushInfo(tr(
                    "mdt_log_plants", n=fmt(len(plants)), dens=fmt(len(plants) / area_ha if area_ha else 0),
                    h=fmt(float(np.mean([p["height"] for p in plants])), 2),
                    d=fmt(float(np.mean([p["diameter"] for p in plants])), 2)))
            else:
                feedback.reportError(tr("mdt_log_no_plants"), fatalError=False)
            if parameters.get(self.OUT_PLANTS) is not None:
                sink, dest = self._sink(parameters, self.OUT_PLANTS, context, make_fields(PLANT_FIELDS),
                                        WKB_POINT, crs, tr("mdt_p_out_plants"), feedback)
                if sink is not None:
                    for p in plants:
                        f = QgsFeature()
                        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(p["x"], p["y"])))
                        f.setAttributes([p["id"], round(p["height"], 3), round(p["mean"], 3),
                                         round(p["area"], 3), round(p["diameter"], 3)])
                        sink.addFeature(f, QgsFeatureSink.Flag.FastInsert)
                    extra[self.OUT_PLANTS] = dest
                    self._style_on_load(context, dest, _RasterStylePostProcessor.create("plants"))
            if parameters.get(self.OUT_CROWNS) is not None:
                sink, dest = self._sink(parameters, self.OUT_CROWNS, context, make_fields(PLANT_FIELDS),
                                        WKB_MULTIPOLYGON, crs, tr("mdt_p_out_crowns"), feedback)
                if sink is not None:
                    geoms = crown_geometries(crowns, gt, proj) if plants else {}
                    for p in plants:
                        g = geoms.get(p["id"])
                        if g is None:
                            continue
                        g.convertToMultiType()
                        f = QgsFeature()
                        f.setGeometry(g)
                        f.setAttributes([p["id"], round(p["height"], 3), round(p["mean"], 3),
                                         round(p["area"], 3), round(p["diameter"], 3)])
                        sink.addFeature(f, QgsFeatureSink.Flag.FastInsert)
                    extra[self.OUT_CROWNS] = dest
                    self._style_on_load(context, dest, _RasterStylePostProcessor.create("crowns"))

        self._style_on_load(context, out_dtm, _RasterStylePostProcessor.create("dtm", dmin, dmax))
        self._style_on_load(context, out_height, _RasterStylePostProcessor.create("height", 0.0, hmax))
        self._style_on_load(context, out_mask, _RasterStylePostProcessor.create("mask"))

        result = {self.OUT_DTM: out_dtm, self.OUT_HEIGHT: out_height}
        if out_mask:
            result[self.OUT_MASK] = out_mask
        result.update(extra)
        return result
