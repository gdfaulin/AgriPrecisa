# -*- coding: utf-8 -*-
"""
AgriPrecisa: small didactic widgets used by the wizard.

PreviewMap : low-resolution live IDW map of the field with the real samples.
"""

import numpy as np

from qgis.PyQt.QtCore import Qt, QPointF, QRectF
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QPen, QBrush
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget
from qgis.core import QgsStyle

from ..core.idw_math import NODATA, idw_grid, MIN_NEIGHBOURS
from ..core.pipeline import field_cell_centres
from ..i18n import tr, fmt

class PreviewMap(QWidget):
    """Low-resolution IDW of one attribute, masked by the field boundary."""

    MAX_CELLS_SIDE = 90

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image = None
        self.extent = None          # (xmin, ymin, xmax, ymax)
        self.mask = None            # bool array (nrow, ncol): cell centre inside boundary
        self.grid = None            # (xmin, ymax, ncol, nrow, res)
        self.points = (np.array([]), np.array([]), np.array([]))
        self.value_range = None
        self.show_points = True
        ramp = QgsStyle.defaultStyle().colorRamp("RdYlGn")
        self.ramp = ramp

    def set_boundary(self, geom):
        """Prepare the preview grid and the inside/outside mask for the boundary."""
        _, _, grid, mask = field_cell_centres(geom, self.MAX_CELLS_SIDE)
        xmin, ymax, ncol, nrow, res = grid
        self.grid = grid
        self.mask = mask
        self.extent = (xmin, ymax - nrow * res, xmin + ncol * res, ymax)

    def set_show_points(self, show):
        self.show_points = bool(show)
        self.update()

    def cell_centres(self):
        """Centres (x, y) of the preview cells that fall inside the field."""
        if self.grid is None:
            return np.array([]), np.array([])
        xmin, ymax, ncol, nrow, res = self.grid
        rows, cols = np.nonzero(self.mask)
        return xmin + (cols + 0.5) * res, ymax - (rows + 0.5) * res

    def set_points(self, xs, ys, zs):
        self.points = (np.asarray(xs, float), np.asarray(ys, float), np.asarray(zs, float))

    def compute(self, power, radius, max_neighbours=0, min_neighbours=MIN_NEIGHBOURS):
        """Recompute the preview. Returns (min, max) of the interpolated values or None."""
        xs, ys, zs = self.points
        if self.grid is None or zs.size == 0:
            self.image, self.value_range = None, None
            self.update()
            return None
        xmin, ymax, ncol, nrow, res = self.grid
        values = idw_grid(xs, ys, zs, xmin, ymax, ncol, nrow, res, power, radius,
                          min_neighbours=min_neighbours, max_neighbours=max_neighbours)
        valid = (values != NODATA) & self.mask
        if valid.any():
            vmin, vmax = float(values[valid].min()), float(values[valid].max())
        else:
            vmin = vmax = None
        img = QImage(ncol, nrow, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        span = (vmax - vmin) if vmin is not None and vmax > vmin else None
        for r in range(nrow):
            for c in range(ncol):
                if not self.mask[r, c]:
                    continue
                v = values[r, c]
                if v == NODATA:
                    color = QColor(200, 200, 200)
                elif span is None:
                    color = self.ramp.color(0.5) if self.ramp else QColor(255, 255, 191)
                else:
                    t = (v - vmin) / span
                    color = self.ramp.color(t) if self.ramp else QColor(int(255 * (1 - t)), int(200 * t), 60)
                img.setPixelColor(c, r, color)
        self.image = img
        self.value_range = (vmin, vmax) if vmin is not None else None
        self.update()
        return self.value_range

    def paintEvent(self, event):
        p = QPainter(self)
        if self.image is None or self.extent is None:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("p3_preview_empty"))
            p.end()
            return
        font = p.font()
        font.setPointSizeF(max(font.pointSizeF() - 1, 7))
        p.setFont(font)
        fh = p.fontMetrics().height()
        legend_h = (fh + 16) if self.value_range else 0
        avail_w, avail_h = self.width(), self.height() - legend_h
        xmin, ymin, xmax, ymax = self.extent
        ew, eh = xmax - xmin, ymax - ymin
        scale = min(avail_w / ew, avail_h / eh)
        dw, dh = ew * scale, eh * scale
        ox, oy = (avail_w - dw) / 2, (avail_h - dh) / 2
        p.drawImage(QRectF(ox, oy, dw, dh), self.image)      # nearest neighbour: shows the cells
        xs, ys, _ = self.points
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255), 0.8))
        p.setBrush(QBrush(QColor(20, 20, 20)))
        rad = 2.2 if xs.size < 400 else 1.4
        for x, y in (zip(xs, ys) if self.show_points else ()):
            if xmin <= x <= xmax and ymin <= y <= ymax:
                p.drawEllipse(QPointF(ox + (x - xmin) * scale, oy + (ymax - y) * scale), rad, rad)

        # colour bar legend: min (red) to max (green)
        if self.value_range:
            vmin, vmax = self.value_range
            bar_w = min(260.0, self.width() - 20.0)
            bx, by = (self.width() - bar_w) / 2, self.height() - legend_h + 2
            steps = 40
            p.setPen(Qt.PenStyle.NoPen)
            for i in range(steps):
                t = i / (steps - 1)
                color = self.ramp.color(t) if self.ramp else QColor(int(255 * (1 - t)), int(200 * t), 60)
                p.setBrush(QBrush(color))
                p.drawRect(QRectF(bx + i * bar_w / steps, by, bar_w / steps + 1, 8))
            pal = self.palette()
            p.setPen(pal.color(pal.ColorRole.WindowText))
            ty = by + 10
            p.drawText(QRectF(bx, ty, bar_w, fh), Qt.AlignmentFlag.AlignLeft, fmt(vmin, 2))
            p.drawText(QRectF(bx, ty, bar_w, fh), Qt.AlignmentFlag.AlignRight, fmt(vmax, 2))
            p.drawText(QRectF(bx, ty, bar_w, fh), Qt.AlignmentFlag.AlignHCenter,
                       tr("p3_preview_n", n=fmt(xs.size)))
        p.end()
