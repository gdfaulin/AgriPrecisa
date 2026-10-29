# -*- coding: utf-8 -*-
"""
AgriPrecisa: small didactic widgets used by the wizard.

WeightCurve : IDW weight versus distance for the current power P and radius.
PreviewMap  : low-resolution live IDW map of the field with the real samples.
"""

import numpy as np

from qgis.PyQt.QtCore import Qt, QPointF, QRectF
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QBrush
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget
from qgis.core import QgsGeometry, QgsPointXY, QgsStyle

from ..core.idw_math import NODATA, idw_grid, relative_weights, snap_extent
from ..i18n import tr, fmt

CURVE_COLOR = QColor(26, 150, 65)        # green of the RdYlGn ramp
REFERENCE_COLOR = QColor(160, 160, 160)
RADIUS_COLOR = QColor(215, 25, 28)       # red of the RdYlGn ramp


class WeightCurve(QWidget):
    """Draws w(d) = (d_min / d)^P from 0 to beyond the search radius."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.power = 2.0
        self.radius = 100.0
        self.spacing = None
        self.d_min = 5.0

    def set_params(self, power, radius, spacing, d_min):
        self.power = power
        self.radius = radius
        self.spacing = spacing
        self.d_min = max(d_min, 0.1)
        self.update()

    def _x_max(self):
        candidates = [v for v in (self.radius * 1.25 if self.radius > 0 else None,
                                  self.spacing * 3 if self.spacing else None) if v]
        return max(candidates) if candidates else 100.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = p.font()
        font.setPointSizeF(max(font.pointSizeF() - 1, 7))
        p.setFont(font)
        fh = p.fontMetrics().height()
        pal = self.palette()
        text_color = pal.color(pal.ColorRole.WindowText)
        # plot area; below it: tick labels, axis title and a one-line legend
        left, right, top, bottom = fh + 18, 12, fh + 4, 3 * fh + 10
        w, h = self.width() - left - right, self.height() - top - bottom
        if w <= 20 or h <= 20:
            p.end()
            return
        x_max = self._x_max()

        def to_px(d, wgt):
            return QPointF(left + d / x_max * w, top + (1 - wgt) * h)

        # axes, ticks and titles
        p.setPen(QPen(text_color, 1))
        p.drawLine(QPointF(left, top + h), QPointF(left + w, top + h))
        p.drawLine(QPointF(left, top), QPointF(left, top + h))
        p.drawText(QRectF(0, top - fh / 2, left - 4, fh), Qt.AlignmentFlag.AlignRight, "1")
        p.drawText(QRectF(0, top + h - fh / 2, left - 4, fh), Qt.AlignmentFlag.AlignRight, "0")
        p.drawText(QRectF(left - 20, top + h + 2, 40, fh), Qt.AlignmentFlag.AlignHCenter, "0")
        p.drawText(QRectF(left, top + h + 2, w, fh), Qt.AlignmentFlag.AlignRight, fmt(x_max) + " m")
        p.drawText(QRectF(left, top + h + 2, w, fh), Qt.AlignmentFlag.AlignHCenter,
                   tr("p3_curve_x"))
        p.save()
        p.translate(2, top + h / 2)
        p.rotate(-90)
        p.drawText(QRectF(-h / 2, 0, h, fh), Qt.AlignmentFlag.AlignHCenter, tr("p3_curve_y"))
        p.restore()

        d = np.linspace(0, x_max, 240)

        def curve(power):
            path = QPainterPath()
            wts = relative_weights(d, power, self.d_min)
            for i, (di, wi) in enumerate(zip(d, wts)):
                pt = to_px(di, wi)
                if i == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            return path

        ref_pen = QPen(REFERENCE_COLOR, 1, Qt.PenStyle.DashLine)
        p.setPen(ref_pen)
        for ref in (1.0, 3.0):
            if abs(ref - self.power) > 0.05:
                p.drawPath(curve(ref))
        p.setPen(QPen(CURVE_COLOR, 2.5))
        p.drawPath(curve(self.power))

        # search radius marker, label above the plot
        if self.radius > 0:
            x = to_px(min(self.radius, x_max), 0).x()
            p.setPen(QPen(RADIUS_COLOR, 1.5, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, top), QPointF(x, top + h))
            p.drawText(QRectF(x - 80, 0, 160, fh), Qt.AlignmentFlag.AlignHCenter,
                       tr("p3_curve_radius") + " " + fmt(self.radius) + " m")

        # legend on its own line under the axis title
        ly = top + h + 2 * fh + 4 + fh / 2
        lx = left
        p.setPen(QPen(CURVE_COLOR, 2.5))
        p.drawLine(QPointF(lx, ly), QPointF(lx + 18, ly))
        p.setPen(text_color)
        label = tr("p3_power_value", p=fmt(self.power, 1))
        p.drawText(QRectF(lx + 22, ly - fh / 2, 120, fh), Qt.AlignmentFlag.AlignLeft, label)
        lx += 30 + p.fontMetrics().horizontalAdvance(label)
        p.setPen(ref_pen)
        p.drawLine(QPointF(lx, ly), QPointF(lx + 18, ly))
        p.setPen(text_color)
        p.drawText(QRectF(lx + 22, ly - fh / 2, 200, fh), Qt.AlignmentFlag.AlignLeft, tr("p3_curve_ref"))
        p.end()


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
        bb = geom.boundingBox()
        side = max(bb.width(), bb.height())
        res = max(side / self.MAX_CELLS_SIDE, 0.5)
        xmin, ymin, xmax, ymax, ncol, nrow = snap_extent(
            bb.xMinimum(), bb.yMinimum(), bb.xMaximum(), bb.yMaximum(), res)
        self.extent = (xmin, ymin, xmax, ymax)
        self.grid = (xmin, ymax, ncol, nrow, res)
        engine = QgsGeometry.createGeometryEngine(geom.constGet())
        engine.prepareGeometry()
        mask = np.zeros((nrow, ncol), dtype=bool)
        for r in range(nrow):
            y = ymax - (r + 0.5) * res
            for c in range(ncol):
                x = xmin + (c + 0.5) * res
                # keep a reference to the point geometry while GEOS uses it: a temporary
                # QgsGeometry is freed too early and the test always returned False
                pt = QgsGeometry.fromPointXY(QgsPointXY(x, y))
                mask[r, c] = engine.intersects(pt.constGet())
        self.mask = mask

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

    def compute(self, power, radius):
        """Recompute the preview. Returns (min, max) of the interpolated values or None."""
        xs, ys, zs = self.points
        if self.grid is None or zs.size == 0:
            self.image, self.value_range = None, None
            self.update()
            return None
        xmin, ymax, ncol, nrow, res = self.grid
        values = idw_grid(xs, ys, zs, xmin, ymax, ncol, nrow, res, power, radius)
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
