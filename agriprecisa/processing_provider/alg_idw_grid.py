# -*- coding: utf-8 -*-
"""AgriPrecisa: Processing algorithm 'IDW vector grid'."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProcessingAlgorithm, QgsProcessingException, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterField, QgsProcessingParameterNumber,
    QgsProcessingParameterFolderDestination, QgsProcessingParameterVectorDestination,
    QgsProcessingLayerPostProcessorInterface, QgsProcessingParameterBoolean,
)

from ..core.compat import SRC_POINT, SRC_POLYGON, FIELD_NUMERIC, NUMBER_DOUBLE
from ..core.pipeline import (
    IdwJob, run_idw_job, crs_in_meters, features_extent, style_graduated, boundary_geometry,
    field_cell_centres, edge_distances, extract_points, buffered,
)
from ..core.idw_math import coverage_distances, suggest_parameters, CV_MIN_VALIDATION
from ..i18n import tr

ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.png")
HELP_URL = "https://github.com/gdfaulin/AgriPrecisa#readme"


class _StylePostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Applies the graduated style when the output is loaded into the project."""

    instance = None  # keeps a reference alive until QGIS uses it

    def __init__(self, field):
        super().__init__()
        self.field = field

    def postProcessLayer(self, layer, context, feedback):
        if layer is not None and layer.fields().indexOf(self.field) >= 0:
            style_graduated(layer, self.field)

    @staticmethod
    def create(field):
        _StylePostProcessor.instance = _StylePostProcessor(field)
        return _StylePostProcessor.instance


class IdwGridAlgorithm(QgsProcessingAlgorithm):
    BOUNDARY = "BOUNDARY"
    POINTS = "POINTS"
    FIELDS = "FIELDS"
    TOLERANCE = "TOLERANCE"
    POWER = "POWER"
    RADIUS = "RADIUS"
    PIXEL = "PIXEL"
    AUTO_PARAMS = "AUTO_PARAMS"
    RASTER_FOLDER = "RASTER_FOLDER"
    OUTPUT = "OUTPUT"

    def createInstance(self):
        return IdwGridAlgorithm()

    def name(self):
        return "idw_vector_grid"

    def displayName(self):
        return tr("alg_name")

    def group(self):
        return tr("alg_group")

    def groupId(self):
        return "interpolation"

    def icon(self):
        return QIcon(ICON)

    def shortHelpString(self):
        return tr("alg_help")

    def helpUrl(self):
        return HELP_URL

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.BOUNDARY, tr("alg_p_boundary"), [SRC_POLYGON]))
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.POINTS, tr("alg_p_points"), [SRC_POINT]))
        self.addParameter(QgsProcessingParameterField(
            self.FIELDS, tr("alg_p_fields"), parentLayerParameterName=self.POINTS,
            type=FIELD_NUMERIC, allowMultiple=True))
        self.addParameter(QgsProcessingParameterNumber(
            self.TOLERANCE, tr("alg_p_tolerance"), NUMBER_DOUBLE, 50.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.POWER, tr("alg_p_power"), NUMBER_DOUBLE, 2.0, minValue=0.1, maxValue=10.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.RADIUS, tr("alg_p_radius"), NUMBER_DOUBLE, 100.0, minValue=0.0))
        self.addParameter(QgsProcessingParameterNumber(
            self.PIXEL, tr("alg_p_pixel"), NUMBER_DOUBLE, 5.0, minValue=0.1))
        self.addParameter(QgsProcessingParameterBoolean(
            self.AUTO_PARAMS, tr("alg_p_auto"), defaultValue=False))
        self.addParameter(QgsProcessingParameterFolderDestination(
            self.RASTER_FOLDER, tr("alg_p_folder")))
        self.addParameter(QgsProcessingParameterVectorDestination(
            self.OUTPUT, tr("alg_p_output"), SRC_POLYGON))

    def processAlgorithm(self, parameters, context, feedback):
        boundary = self.parameterAsSource(parameters, self.BOUNDARY, context)
        points = self.parameterAsSource(parameters, self.POINTS, context)
        if boundary is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.BOUNDARY))
        if points is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.POINTS))
        # parameterAsStrings replaces the deprecated parameterAsFields (QGIS >= 3.32)
        if hasattr(self, "parameterAsStrings"):
            fields = self.parameterAsStrings(parameters, self.FIELDS, context)
        else:
            fields = self.parameterAsFields(parameters, self.FIELDS, context)
        if not fields:
            raise QgsProcessingException(tr("p2_err_none"))

        for src in (boundary, points):
            if not crs_in_meters(src.sourceCrs()):
                raise QgsProcessingException(
                    tr("alg_err_crs", name=src.sourceName(), crs=src.sourceCrs().authid()))

        extent = features_extent(boundary.getFeatures())
        if extent is None:
            raise QgsProcessingException(tr("p1_err_empty"))

        folder = self.parameterAsString(parameters, self.RASTER_FOLDER, context)
        os.makedirs(folder, exist_ok=True)
        output = self.parameterAsOutputLayer(parameters, self.OUTPUT, context)

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        power = self.parameterAsDouble(parameters, self.POWER, context)
        radius = self.parameterAsDouble(parameters, self.RADIUS, context)
        params = [(power, radius)] * len(fields)
        if self.parameterAsBoolean(parameters, self.AUTO_PARAMS, context):
            params = self.cross_validated_params(boundary, points, fields, extent, tolerance,
                                                 power, radius, context, feedback)

        job = IdwJob(
            params=params,
            boundary_input=parameters[self.BOUNDARY],
            boundary_extent=extent,
            boundary_crs=boundary.sourceCrs(),
            items=[(points, f) for f in fields],
            tolerance=tolerance,
            power=power,
            radius=radius,
            pixel=self.parameterAsDouble(parameters, self.PIXEL, context),
            raster_folder=folder,
            output_path=output,
        )
        result = run_idw_job(job, context, feedback)

        if context.willLoadLayerOnCompletion(output) and result["layers"]:
            details = context.layerToLoadOnCompletionDetails(output)
            details.setPostProcessor(_StylePostProcessor.create(result["layers"][0]["mean_field"]))

        for info in result["layers"]:
            feedback.pushInfo(tr("done_line", label=info["label"], n=info["n"]))
        return {self.OUTPUT: output, self.RASTER_FOLDER: folder}

    def cross_validated_params(self, boundary, points, fields, extent, tolerance,
                               power, radius, context, feedback):
        """
        (power, radius) for each field chosen by its own cross-validation; each attribute
        has its own spatial dependence and variability. Falls back to the given values.
        """
        geom = boundary_geometry(boundary.getFeatures())
        px, py, _, _ = field_cell_centres(geom)
        rect = buffered(extent, tolerance)
        crs = boundary.sourceCrs()
        out = []
        for f in fields:
            if feedback.isCanceled():
                raise QgsProcessingException(tr("canceled"))
            label = f"{f} ({points.sourceName()})"
            feedback.pushInfo(tr("cv_all_progress", label=label))
            xs, ys, zs = extract_points(points, f, rect, crs, context.transformContext())
            typical, cover, nearest = coverage_distances(px, py, xs, ys, return_nearest=True)
            res = None
            if cover:
                res = suggest_parameters(xs, ys, zs, edge_distances(geom, xs, ys), cover, typical,
                                         pixel_nearest=nearest)
            if res is None or res.get("error"):
                reason = (tr("cv_reason_cover") if res is None else
                          tr("cv_few", n=res["n_val"], min=CV_MIN_VALIDATION)
                          if res["error"] == "few" else tr("cv_failed"))
                feedback.reportError(tr("alg_log_auto_fail", label=label, reason=reason,
                                        p=f"{power:g}", r=f"{radius:g} m"), fatalError=False)
                out.append((power, radius))
                continue
            feedback.pushInfo(tr("alg_log_auto", label=label, p=f"{res['power']:g}",
                                 r=f"{res['radius']:.1f}", rmse=f"{res['best_rmse']:.4g}"))
            out.append((res["power"], res["radius"]))
        return out
