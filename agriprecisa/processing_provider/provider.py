# -*- coding: utf-8 -*-
"""AgriPrecisa: Processing provider (Processing Toolbox entry)."""

import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .alg_idw_grid import IdwGridAlgorithm

ICON = os.path.join(os.path.dirname(os.path.dirname(__file__)), "icon.png")


class AgriPrecisaProvider(QgsProcessingProvider):
    def loadAlgorithms(self):
        self.addAlgorithm(IdwGridAlgorithm())

    def id(self):
        return "agriprecisa"

    def name(self):
        return "AgriPrecisa"

    def icon(self):
        return QIcon(ICON)
