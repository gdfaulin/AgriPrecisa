# -*- coding: utf-8 -*-
"""
AgriPrecisa: small didactic widgets used by the wizard.

WeightCurve   : IDW weight 1/d^P relative to the weight at the typical pixel-to-sample
                distance (Shepard, 1968), with distance ticks and the search radius.
InfluenceBars : share of each neighbouring sample (lambda = w_i / sum w_j, 100 % in total)
                in the estimate of a typical pixel of the field.
PreviewMap    : low-resolution live IDW map of the field with the real samples.
"""

import math

import numpy as np

from qgis.PyQt.QtCore import Qt, QPointF, QRectF
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QPainterPath, QPen, QBrush
from qgis.PyQt.QtWidgets import QSizePolicy, QWidget
from qgis.core import QgsStyle

from ..core.idw_math import NODATA, idw_grid, relative_weights, normalized_weights
from ..core.pipeline import field_cell_centres
from ..i18n import tr, fmt

CURVE_COLOR = QColor(26, 150, 65)        # green of the RdYlGn ramp
RADIUS_COLOR = QColor(215, 25, 28)       # red of the RdYlGn ramp
REF_COLOR = QColor(120, 120, 120)
Y_MAX = 4.0                              # relative weight axis is cut here (it tends to infinity)
MAX_BARS = 6


def nice_step(span, target=5):
    """Round tick step (1, 2 or 5 x 10^n) giving about ``target`` intervals."""
    if span <= 0:
        return 1.0
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _small_font(painter):
    font = painter.font()
    font.setPointSizeF(max(font.pointSizeF() - 1, 7))
    painter.setFont(font)
    return painter.fontMetrics().height()


class WeightCurve(QWidget):
    """w(d) / w(d_ref) = (d_ref / d)^P, from 0 to beyond the search radius."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(270, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setToolTip(tr("p3_curve_tip"))
        self.power = 2.0
        self.radius = 100.0
        self.d_ref = 10.0

    def set_params(self, power, radius, d_ref):
        self.power = power
        self.radius = radius
        self.d_ref = max(d_ref or 1.0, 0.1)
        self.update()

    def x_max(self):
        base = self.radius if self.radius > 0 else 4 * self.d_ref
        return max(base * 1.15, 2 * self.d_ref)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fh = _small_font(p)
        pal = self.palette()
        text_color = pal.color(pal.ColorRole.WindowText)
        left, right, top, bottom = fh + 26, 10, fh + 6, 3 * fh + 12
        w, h = self.width() - left - right, self.height() - top - bottom
        if w <= 20 or h <= 20:
            p.end()
            return
        x_max = self.x_max()

        def to_px(d, wgt):
            return QPointF(left + d / x_max * w, top + (1 - min(wgt, Y_MAX) / Y_MAX) * h)

        # axes
        p.setPen(QPen(text_color, 1))
        p.drawLine(QPointF(left, top + h), QPointF(left + w, top + h))
        p.drawLine(QPointF(left, top), QPointF(left, top + h))
        # y ticks: 0 .. Y_MAX, the top one marks that the axis is cut
        for v in range(int(Y_MAX) + 1):
            y = to_px(0, v).y()
            p.drawLine(QPointF(left - 4, y), QPointF(left, y))
            label = fmt(v) if v < Y_MAX else "≥" + fmt(v)
            p.drawText(QRectF(0, y - fh / 2, left - 6, fh), Qt.AlignmentFlag.AlignRight, label)
        # x ticks with a round step
        step = nice_step(x_max)
        t = 0.0
        while t <= x_max + 1e-9:
            x = to_px(t, 0).x()
            p.drawLine(QPointF(x, top + h), QPointF(x, top + h + 4))
            p.drawText(QRectF(x - 30, top + h + 4, 60, fh), Qt.AlignmentFlag.AlignHCenter, fmt(t))
            t += step
        p.drawText(QRectF(left, top + h + fh + 4, w, fh), Qt.AlignmentFlag.AlignHCenter,
                   tr("p3_curve_x"))
        p.save()
        p.translate(2, top + h / 2)
        p.rotate(-90)
        p.drawText(QRectF(-h / 2, 0, h, fh), Qt.AlignmentFlag.AlignHCenter, tr("p3_curve_y"))
        p.restore()

        # curve (starts where it enters the cut axis, so it never draws a fake plateau)
        d0 = self.d_ref * (1.0 / Y_MAX) ** (1.0 / self.power)    # where the weight equals Y_MAX
        d = np.linspace(d0, x_max, 240)
        wts = relative_weights(d, self.power, self.d_ref)
        path = QPainterPath()
        for i, (di, wi) in enumerate(zip(d, wts)):
            pt = to_px(di, wi)
            if i == 0:
                path.moveTo(pt)
            else:
                path.lineTo(pt)
        p.setPen(QPen(CURVE_COLOR, 2.5))
        p.drawPath(path)

        # reference point: weight 1 at the typical pixel-to-sample distance
        ref = to_px(self.d_ref, 1.0)
        p.setBrush(QBrush(CURVE_COLOR))
        p.drawEllipse(ref, 3.5, 3.5)
        p.setPen(text_color)
        text = tr("p3_curve_ref_point", d=fmt(self.d_ref, 1))
        tw = p.fontMetrics().horizontalAdvance(text)
        tx = min(ref.x() + 6, left + w - tw)            # keep the label inside the plot
        p.drawText(QRectF(tx, ref.y() - fh - 4, tw + 4, fh), Qt.AlignmentFlag.AlignLeft, text)

        # search radius
        if self.radius > 0:
            x = to_px(min(self.radius, x_max), 0).x()
            p.setPen(QPen(RADIUS_COLOR, 1.5, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(x, top), QPointF(x, top + h))
            p.setPen(RADIUS_COLOR)
            p.drawText(QRectF(x - 80, 0, 160, fh), Qt.AlignmentFlag.AlignHCenter,
                       tr("p3_curve_radius") + " " + fmt(self.radius) + " m")

        # one-line legend
        ly = top + h + 2 * fh + 8 + fh / 2
        p.setPen(QPen(CURVE_COLOR, 2.5))
        p.drawLine(QPointF(left, ly), QPointF(left + 18, ly))
        p.setPen(text_color)
        p.drawText(QRectF(left + 22, ly - fh / 2, w, fh), Qt.AlignmentFlag.AlignLeft,
                   tr("p3_power_value", p=fmt(self.power, 1)))
        p.end()


class InfluenceBars(QWidget):
    """Horizontal bars: share (%) of each neighbour in the estimate of a typical pixel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(210, 180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setToolTip(tr("p3_bars_tip"))
        self.distances = np.array([])
        self.power = 2.0

    def set_data(self, distances, power):
        self.distances = np.asarray(distances, float)
        self.power = power
        self.update()

    def shares(self):
        """(rows, rest): up to MAX_BARS (distance, share) and the share of the others."""
        lam = normalized_weights(self.distances, self.power)
        rows = list(zip(self.distances[:MAX_BARS], lam[:MAX_BARS]))
        rest = float(lam[MAX_BARS:].sum()) if lam.size > MAX_BARS else 0.0
        return rows, rest

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fh = _small_font(p)
        pal = self.palette()
        text_color = pal.color(pal.ColorRole.WindowText)
        if self.distances.size == 0:
            p.setPen(text_color)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       tr("p3_bars_empty"))
            p.end()
            return
        rows, rest = self.shares()
        labels = [tr("p3_bars_row", k=k + 1, d=fmt(d, 1)) for k, (d, _) in enumerate(rows)]
        values = [s for _, s in rows]
        if rest > 0:
            labels.append(tr("p3_bars_rest", n=fmt(self.distances.size - MAX_BARS)))
            values.append(rest)
        label_w = max(p.fontMetrics().horizontalAdvance(t) for t in labels) + 8
        pct_w = p.fontMetrics().horizontalAdvance("100%") + 6
        top = 2
        bottom = fh + 6
        bar_area = self.width() - label_w - pct_w - 6
        row_h = min(2 * fh, (self.height() - top - bottom) / max(len(labels), 1))
        for i, (text, v) in enumerate(zip(labels, values)):
            y = top + i * row_h
            p.setPen(text_color)
            p.drawText(QRectF(0, y, label_w - 4, row_h), Qt.AlignmentFlag.AlignRight |
                       Qt.AlignmentFlag.AlignVCenter, text)
            bw = max(bar_area * v, 1.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(CURVE_COLOR if i < len(rows) else REF_COLOR))
            p.drawRect(QRectF(label_w, y + row_h * 0.2, bw, row_h * 0.6))
            p.setPen(text_color)
            p.drawText(QRectF(label_w + bw + 4, y, pct_w + 20, row_h),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       fmt(v * 100) + "%")
        p.setPen(text_color)
        p.drawText(QRectF(0, self.height() - fh - 2, self.width(), fh), Qt.AlignmentFlag.AlignHCenter,
                   tr("p3_bars_total", n=fmt(self.distances.size)))
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
