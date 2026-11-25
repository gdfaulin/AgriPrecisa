# -*- coding: utf-8 -*-
"""AgriPrecisa: Processing algorithm 'DTM and plant height in row crops (from the DSM)'."""

import os

import numpy as np
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingException, QgsProcessingParameterRasterLayer,
    QgsProcessingParameterNumber, QgsProcessingParameterBoolean, QgsProcessingParameterEnum,
    QgsProcessingParameterRasterDestination, QgsProcessingLayerPostProcessorInterface,
    QgsProject, QgsStyle, QgsColorRampShader, QgsRasterShader,
    QgsSingleBandPseudoColorRenderer, QgsPalettedRasterRenderer,
)

from ..core.compat import NUMBER_DOUBLE, SHADER_LINEAR
from ..core import mdt_math as mm
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


def style_soil_mask(layer):
    """0 = plants (green), 1 = soil (brown)."""
    if layer is None or not layer.isValid():
        return
    classes = [QgsPalettedRasterRenderer.Class(0, QColor("#2e7d32"), tr("mdt_class_plants")),
               QgsPalettedRasterRenderer.Class(1, QColor("#a1785c"), tr("mdt_class_soil"))]
    layer.setRenderer(QgsPalettedRasterRenderer(layer.dataProvider(), 1, classes))
    layer.triggerRepaint()


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
            style_soil_mask(layer)

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
            self.OUT_MASK, tr("mdt_p_out_mask"), defaultValue=default("Mascara_solo.tif"),
            optional=True, createByDefault=True))

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
            mask = np.where(valid, soil.astype("uint8"), MASK_NODATA).astype("uint8")
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

        _RasterStylePostProcessor.alive = []
        self._style_on_load(context, out_dtm, _RasterStylePostProcessor.create("dtm", dmin, dmax))
        self._style_on_load(context, out_height, _RasterStylePostProcessor.create("height", 0.0, hmax))
        self._style_on_load(context, out_mask, _RasterStylePostProcessor.create("mask"))

        result = {self.OUT_DTM: out_dtm, self.OUT_HEIGHT: out_height}
        if out_mask:
            result[self.OUT_MASK] = out_mask
        return result
