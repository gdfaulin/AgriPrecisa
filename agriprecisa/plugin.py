# -*- coding: utf-8 -*-
"""AgriPrecisa: menu, toolbar and Processing provider registration."""

import os

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QIcon, QDesktopServices
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication

from .i18n import tr
from .processing_provider.provider import AgriPrecisaProvider

PLUGIN_DIR = os.path.dirname(__file__)
MENU = "&AgriPrecisa"
DOCS_URL = "https://github.com/gdfaulin/AgriPrecisa#readme"


class AgriPrecisaPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.toolbar = None
        self.actions = []

    # Processing --------------------------------------------------------
    def initProcessing(self):
        provider = AgriPrecisaProvider()
        # addProvider returns False (and QGIS deletes the object) when a provider
        # with the same id already exists; keep no reference to it in that case.
        if QgsApplication.processingRegistry().addProvider(provider):
            self.provider = provider
        else:
            self.provider = None

    # GUI ---------------------------------------------------------------
    def initGui(self):
        self.initProcessing()
        self.toolbar = self.iface.addToolBar("AgriPrecisa")
        self.toolbar.setObjectName("AgriPrecisaToolbar")

        self._add_action(os.path.join(PLUGIN_DIR, "icons", "idw.png"),
                         tr("action_idw"), tr("action_idw_tip"), self.run_idw, toolbar=True)
        self._add_action(os.path.join(PLUGIN_DIR, "icons", "help.png"),
                         tr("action_help"), tr("action_help"), self.open_docs, toolbar=False)

    def _add_action(self, icon_path, text, tip, callback, toolbar):
        action = QAction(QIcon(icon_path), text, self.iface.mainWindow())
        action.setToolTip(tip)
        action.setStatusTip(tip)
        action.triggered.connect(callback)
        self.iface.addPluginToVectorMenu(MENU, action)
        if toolbar:
            self.toolbar.addAction(action)
        self.actions.append(action)
        return action

    def unload(self):
        for action in self.actions:
            self.iface.removePluginVectorMenu(MENU, action)
        self.actions = []
        if self.toolbar is not None:
            self.toolbar.deleteLater()
            self.toolbar = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

    # Actions -----------------------------------------------------------
    def run_idw(self):
        from .gui.idw_wizard import run_wizard
        run_wizard(self.iface)

    def open_docs(self):
        QDesktopServices.openUrl(QUrl(DOCS_URL))
