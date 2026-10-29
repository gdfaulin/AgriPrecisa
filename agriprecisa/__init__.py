# -*- coding: utf-8 -*-
"""
AgriPrecisa: precision agriculture tools for QGIS.

Copyright (C) 2026 Gustavo Di Chiacchio Faulin
Licensed under the GNU General Public License v2 or later (see LICENSE).
"""


def classFactory(iface):
    from .plugin import AgriPrecisaPlugin
    return AgriPrecisaPlugin(iface)
