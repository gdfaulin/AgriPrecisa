# -*- coding: utf-8 -*-
"""
AgriPrecisa: constants that changed names between QGIS 3.x and QGIS 4.x.

Each value is resolved once, trying the newer (scoped) name first and
falling back to the older one.
"""

from qgis.core import (
    Qgis, QgsWkbTypes, QgsUnitTypes, QgsProcessing, QgsFeatureRequest,
    QgsProcessingParameterField, QgsProcessingParameterNumber, QgsVectorFileWriter,
)


def _first(*getters):
    for get in getters:
        try:
            return get()
        except AttributeError:
            continue
    raise AttributeError("No compatible constant found")


GEOM_POINT = _first(lambda: Qgis.GeometryType.Point, lambda: QgsWkbTypes.PointGeometry)
GEOM_POLYGON = _first(lambda: Qgis.GeometryType.Polygon, lambda: QgsWkbTypes.PolygonGeometry)
UNIT_METERS = _first(lambda: Qgis.DistanceUnit.Meters, lambda: QgsUnitTypes.DistanceMeters)
NO_GEOMETRY = _first(lambda: Qgis.FeatureRequestFlag.NoGeometry,
                     lambda: QgsFeatureRequest.Flag.NoGeometry,
                     lambda: QgsFeatureRequest.NoGeometry)

SRC_POINT = _first(lambda: Qgis.ProcessingSourceType.VectorPoint,
                   lambda: QgsProcessing.TypeVectorPoint)
SRC_POLYGON = _first(lambda: Qgis.ProcessingSourceType.VectorPolygon,
                     lambda: QgsProcessing.TypeVectorPolygon)
FIELD_NUMERIC = _first(lambda: Qgis.ProcessingFieldParameterDataType.Numeric,
                       lambda: QgsProcessingParameterField.Numeric)
NUMBER_DOUBLE = _first(lambda: Qgis.ProcessingNumberParameterType.Double,
                       lambda: QgsProcessingParameterNumber.Double)
NUMBER_INTEGER = _first(lambda: Qgis.ProcessingNumberParameterType.Integer,
                        lambda: QgsProcessingParameterNumber.Integer)
WRITER_NO_ERROR = _first(lambda: QgsVectorFileWriter.WriterError.NoError,
                         lambda: QgsVectorFileWriter.NoError)


def _field_int():
    """Integer field type: QMetaType from QGIS 3.38 on (required by Qt6/QGIS 4), else QVariant."""
    if Qgis.QGIS_VERSION_INT >= 33800:
        from qgis.PyQt.QtCore import QMetaType
        return QMetaType.Type.Int
    from qgis.PyQt.QtCore import QVariant
    return QVariant.Int


FIELD_INT = _field_int()
