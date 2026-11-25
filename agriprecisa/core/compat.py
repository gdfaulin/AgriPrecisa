# -*- coding: utf-8 -*-
"""
AgriPrecisa: constants that changed names between QGIS 3.x and QGIS 4.x.

Each value is resolved once, trying the newer (scoped) name first and
falling back to the older one. Every name is written in the scoped form
(Class.EnumType.Member), which works on QGIS 3.x (PyQt5) and is what the Qt6
checker of plugins.qgis.org requires.
"""

from qgis.core import (
    Qgis, QgsWkbTypes, QgsUnitTypes, QgsProcessing, QgsFeatureRequest,
    QgsProcessingParameterField, QgsProcessingParameterNumber, QgsVectorFileWriter,
    QgsColorRampShader,
)


def _first(*getters):
    for get in getters:
        try:
            return get()
        except AttributeError:
            continue
    raise AttributeError("No compatible constant found")


GEOM_POINT = _first(lambda: Qgis.GeometryType.Point, lambda: QgsWkbTypes.GeometryType.PointGeometry)
GEOM_POLYGON = _first(lambda: Qgis.GeometryType.Polygon, lambda: QgsWkbTypes.GeometryType.PolygonGeometry)
UNIT_METERS = _first(lambda: Qgis.DistanceUnit.Meters, lambda: QgsUnitTypes.DistanceUnit.DistanceMeters)
NO_GEOMETRY = _first(lambda: Qgis.FeatureRequestFlag.NoGeometry,
                     lambda: QgsFeatureRequest.Flag.NoGeometry)

SRC_POINT = _first(lambda: Qgis.ProcessingSourceType.VectorPoint,
                   lambda: QgsProcessing.SourceType.TypeVectorPoint)
SRC_POLYGON = _first(lambda: Qgis.ProcessingSourceType.VectorPolygon,
                     lambda: QgsProcessing.SourceType.TypeVectorPolygon)
FIELD_NUMERIC = _first(lambda: Qgis.ProcessingFieldParameterDataType.Numeric,
                       lambda: QgsProcessingParameterField.DataType.Numeric)
NUMBER_DOUBLE = _first(lambda: Qgis.ProcessingNumberParameterType.Double,
                       lambda: QgsProcessingParameterNumber.Type.Double)
NUMBER_INTEGER = _first(lambda: Qgis.ProcessingNumberParameterType.Integer,
                        lambda: QgsProcessingParameterNumber.Type.Integer)
SHADER_LINEAR = _first(lambda: Qgis.ShaderInterpolationMethod.Linear,
                       lambda: QgsColorRampShader.Type.Interpolated)
SHADER_CONTINUOUS = _first(lambda: Qgis.ShaderClassificationMethod.Continuous,
                           lambda: QgsColorRampShader.ClassificationMode.Continuous)
WRITER_NO_ERROR = QgsVectorFileWriter.WriterError.NoError


def _field_int():
    """Integer field type: QMetaType from QGIS 3.38 on (required by Qt6/QGIS 4), else QVariant."""
    if Qgis.QGIS_VERSION_INT >= 33800:
        from qgis.PyQt.QtCore import QMetaType
        return QMetaType.Type.Int
    from qgis.PyQt.QtCore import QVariant
    return QVariant.Int


FIELD_INT = _field_int()
