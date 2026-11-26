# -*- coding: utf-8 -*-
"""
AgriPrecisa: step-by-step wizard for "DTM and plant height in row crops".

1. DSM, optional RGB image, working resolution and row spacing, measured on a 30 m window
   (clicks on several rows, or automatic detection drawn over the image).
2. DTM adjustment: DSM of the window, DTM preview and a profile across the rows, with
   sliders for the window factor, the soil tolerance and the slope (0 = automatic).
3. Plant mask: translucent mask over the RGB (or the DSM) of the window, with sliders for
   the minimum plant height and the transparency.
4. Outputs: each layer can be turned off, with its own path and file name.

Previews use only a window of the DSM, so they stay fast on large fields. The Processing
algorithm agriprecisa:dtm_row_crops does the final work on the whole DSM.
"""

import math
import os
import traceback

import numpy as np
from qgis.PyQt.QtCore import Qt, QCoreApplication, QPointF, QRectF, pyqtSignal
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QPen, QPainterPath
from qgis.PyQt.QtWidgets import (
    QDialog, QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel,
    QPushButton, QDoubleSpinBox, QSpinBox, QCheckBox, QMessageBox, QProgressDialog,
    QTextBrowser, QGroupBox, QSlider, QWidget, QSizePolicy, QScrollArea, QFrame, QToolButton,
    QComboBox,
)
from qgis.core import (
    QgsSettings, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsProcessingContext,
    QgsProcessingFeedback, QgsProcessingException,
)
from qgis.gui import QgsMapLayerComboBox, QgsFileWidget

from ..core import mdt_math as mm
from ..core.compat import LAYER_FILTER_RASTER
from ..i18n import tr, fmt
from ..processing_provider.alg_dtm_rows import (
    style_pseudocolor, style_plant_mask, style_plant_polygons,
)

LAST_FOLDER_KEY = "AgriPrecisa/mdt_last_output_folder"
WINDOW_SIDE = 30.0            # metres, side of the preview window without zoom
ZOOM_SIDES = (30.0, 15.0, 7.5, 3.75)   # sides of the window for each zoom level (2.2.1)
DISPLAY_PIXELS = 700          # at most this many pixels across the shown window
OUTLINE_RGB = (255, 220, 0)   # plant mask shown as outline (2.2.1)
OVERVIEW_PIXELS = 320         # longest side of the field miniature
FACTOR_RANGE = (1.0, 3.0)
TOL_RANGE = (0.02, 1.00)
SLOPE_RANGE = (0, 100)        # percent; 0 = automatic (opening) or 30 percent (slope-based filter)
FURROW_RANGE = (0.0, 1.0)     # furrow removal: sigma as a fraction of the row spacing; 0 = off
PLANT_RANGE = (0.05, 3.00)
DEFAULT_TOLERANCE = 0.25
DEFAULT_ALPHA = 50            # percent of transparency of the mask
PLANT_RGBA = (30, 200, 60)
NODATA_RGB = (225, 225, 225)
OUTPUTS = [  # key, label key, file suffix, file filter
    ("OUT_DTM", "mdt_p_out_dtm", "_MDT.tif", "GeoTIFF (*.tif *.TIF)"),
    ("OUT_HEIGHT", "mdt_p_out_height", "_Altura.tif", "GeoTIFF (*.tif *.TIF)"),
    ("OUT_MASK", "mdt_p_out_mask", "_Mascara_planta.tif", "GeoTIFF (*.tif *.TIF)"),
    ("OUT_POLYGONS", "mdt_p_out_polygons", "_Poligonos_planta.shp", "ESRI Shapefile (*.shp *.SHP)"),
]


def safe_name(name):
    """Layer name usable in a file name on any system."""
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name).strip("_") or "MDS"


def default_outputs(dsm_name, folder):
    base = safe_name(dsm_name)
    return {key: os.path.join(folder, base + suffix) if folder else ""
            for key, _label, suffix, _f in OUTPUTS}


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------
def rgb_image(rgb):
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


def rgba_image(rgba):
    rgba = np.ascontiguousarray(rgba, dtype=np.uint8)
    h, w, _ = rgba.shape
    return QImage(rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888).copy()


def gray_relief(values, valid, lohi=None):
    """Grey from low (dark) to high (light); ``lohi`` fixes the stretch (to compare images)."""
    out = np.empty(values.shape + (3,), np.uint8)
    out[:] = NODATA_RGB
    if valid.any():
        lo, hi = lohi if lohi is not None else np.percentile(values[valid], (2, 98))
        t = np.clip((values - lo) / (hi - lo if hi > lo else 1.0), 0, 1)
        g = (30 + 215 * np.nan_to_num(t)).astype(np.uint8)
        out[valid] = np.stack([g[valid]] * 3, axis=-1)
    return out


def stretch_rgb(bands, valid):
    """
    uint8 RGB from 3 bands. 8-bit images keep their colours; other data types get one common
    2 to 98 percentile stretch for the three bands (a stretch per band would change the colours).
    """
    out = np.empty(bands[0].shape + (3,), np.uint8)
    out[:] = NODATA_RGB
    if not valid.any():
        return out
    stack = np.stack([b.astype("float64") for b in bands[:3]], axis=-1)
    if all(b.dtype == np.uint8 for b in bands[:3]):
        scaled = stack
    else:
        lo, hi = np.percentile(stack[valid], (2, 98))
        scaled = np.clip((stack - lo) / (hi - lo if hi > lo else 1.0), 0, 1) * 255
    out[valid] = scaled[valid].astype(np.uint8)
    return out


def display_res(native, side):
    """Pixel used to show a window of ``side`` metres: the native one, unless it is too fine."""
    return max(native, side / DISPLAY_PIXELS)


def mask_overlay(plants, valid, alpha_percent, outline=False):
    """
    Plant mask over the image: translucent fill, or only the outline of the plant patches
    (keeps the image visible and shows the edges). Soil and no data are fully transparent.
    """
    rgba = np.zeros(plants.shape + (4,), np.uint8)
    shown = plants & valid
    if outline:
        from scipy import ndimage
        # border_value=1: patches cut by the edge of the window are not outlined along it
        shown = shown & ~ndimage.binary_erosion(shown, border_value=1)
        rgba[..., 0], rgba[..., 1], rgba[..., 2] = OUTLINE_RGB
    else:
        rgba[..., 0], rgba[..., 1], rgba[..., 2] = PLANT_RGBA
    rgba[..., 3] = np.where(shown, int(round(255 * (100 - alpha_percent) / 100.0)), 0)
    return rgba


# ---------------------------------------------------------------------------
# Data: DSM and RGB windows read on demand
# ---------------------------------------------------------------------------
class WindowSource:
    """Reads the field miniature and windows of the DSM (and of the RGB, if any) with GDAL."""

    def __init__(self, dsm_layer, rgb_layer, zero_nodata):
        from osgeo import gdal
        self.dsm = gdal.Open(dsm_layer.source())
        if self.dsm is None:
            raise QgsProcessingException(tr("mdt_err_open"))
        self.rgb = gdal.Open(rgb_layer.source()) if rgb_layer is not None else None
        self.wkt = self.dsm.GetProjection()
        self.zero = zero_nodata
        nd = self.dsm.GetRasterBand(1).GetNoDataValue()
        self.nd = 0 if nd is None and zero_nodata else nd
        gt = self.dsm.GetGeoTransform()
        self.native = abs(gt[1])
        xmin, ymax = gt[0], gt[3]
        self.extent = (xmin, ymax + self.dsm.RasterYSize * gt[5], xmin + self.dsm.RasterXSize * gt[1], ymax)
        self._overview = None

    def _clean(self, arr):
        arr = arr.astype("float64")
        arr[arr == -9999] = np.nan
        if self.zero:
            arr[arr == 0] = np.nan
        return arr

    def overview(self):
        """(rgb uint8 of the DSM in grey, extent, centre of the data); computed once."""
        if self._overview is not None:
            return self._overview
        from osgeo import gdal
        xmin, ymin, xmax, ymax = self.extent
        step = max(xmax - xmin, ymax - ymin) / OVERVIEW_PIXELS
        ds = gdal.Warp("", self.dsm, format="MEM", xRes=step, yRes=step, resampleAlg="average",
                       srcNodata=self.nd, dstNodata=-9999)
        arr = self._clean(ds.GetRasterBand(1).ReadAsArray())
        valid = np.isfinite(arr)
        gt = ds.GetGeoTransform()
        ext = (gt[0], gt[3] + arr.shape[0] * gt[5], gt[0] + arr.shape[1] * gt[1], gt[3])
        if valid.any():
            r, c = np.argwhere(valid).mean(axis=0)
            centre = (gt[0] + (c + 0.5) * gt[1], gt[3] + (r + 0.5) * gt[5])
        else:
            centre = ((ext[0] + ext[2]) / 2, (ext[1] + ext[3]) / 2)
        self._overview = (gray_relief(arr, valid), ext, centre)
        return self._overview

    def dsm_window(self, bounds, res, resample="min"):
        """DSM (NaN = no data) over bounds (xmin, ymin, xmax, ymax) at ``res``."""
        from osgeo import gdal
        ds = gdal.Warp("", self.dsm, format="MEM", xRes=res, yRes=res, resampleAlg=resample,
                       srcNodata=self.nd, dstNodata=-9999, outputBounds=bounds)
        return self._clean(ds.GetRasterBand(1).ReadAsArray())

    def background(self, bounds, width, height):
        """RGB image of the window (the RGB layer, or the DSM in grey when there is none)."""
        from osgeo import gdal
        if self.rgb is not None:
            ds = gdal.Warp("", self.rgb, format="MEM", width=width, height=height,
                           outputBounds=bounds, dstSRS=self.wkt, resampleAlg="average")
            n = ds.RasterCount
            bands = [ds.GetRasterBand(min(i, n)).ReadAsArray() for i in (1, 2, 3)]
            valid = np.ones(bands[0].shape, bool)
            if n >= 4:                                   # alpha band
                valid = ds.GetRasterBand(4).ReadAsArray() > 0
            nd = ds.GetRasterBand(1).GetNoDataValue()
            if nd is not None:
                valid &= bands[0] != nd
            return stretch_rgb(bands, valid)
        ds = gdal.Warp("", self.dsm, format="MEM", width=width, height=height, outputBounds=bounds,
                       resampleAlg="average", srcNodata=self.nd, dstNodata=-9999)
        arr = self._clean(ds.GetRasterBand(1).ReadAsArray())
        return gray_relief(arr, np.isfinite(arr))


def window_bounds(centre, side=WINDOW_SIDE, margin=0.0):
    cx, cy = centre
    h = side / 2 + margin
    return (cx - h, cy - h, cx + h, cy + h)


class Preview:
    """DTM of the current window with the current settings (cached per window and settings)."""

    def __init__(self):
        self.key = None
        self.dsm_key = None

    def compute(self, wizard):
        w = wizard
        dsm_key = (w.centre, w.resolution, w.spacing, id(w.source), w.window_side)
        if dsm_key != self.dsm_key:
            self.dsm_key = dsm_key
            # regression 2.2.1: the margin and the window are whole pixels, so the cropped
            # preview has exactly side / resolution pixels and lines up with the image
            res = w.resolution
            self.margin_px = int(math.ceil((w.spacing * FACTOR_RANGE[1] / 2) / res)) + 1
            n = max(int(round(w.window_side / res)), 1)
            half = n * res / 2 + self.margin_px * res
            cx, cy = w.centre
            self.dsm = w.source.dsm_window((cx - half, cy - half, cx + half, cy + half), res)
            self.opening_key = None
            self.key = None
        key = (dsm_key, w.method, w.factor, w.tolerance, w.slope, w.furrows)
        if key == self.key:
            return self
        self.key = key
        valid = np.isfinite(self.dsm)
        window = max(mm.window_pixels(w.spacing, w.factor, w.resolution), 3)
        opening = None
        if w.method == mm.METHOD_OPENING:
            if self.opening_key != (dsm_key, w.factor):
                self.opening_key = (dsm_key, w.factor)
                self.opening = mm.ground_surface(self.dsm, valid, window)
            opening = self.opening
        soil, self.slope_used, _op = mm.classify_ground(self.dsm, valid, w.resolution, window, w.tolerance,
                                                        w.slope, w.method, opening=opening)
        filled = mm.fill_nearest(np.where(soil, self.dsm, np.nan))
        dtm = mm.smooth_dtm(filled, self.dsm, valid, window)
        dtm, height = mm.apply_furrows(dtm, self.dsm, valid, w.resolution, w.spacing, w.furrows)
        m = self.margin_px
        crop = (slice(m, -m or None), slice(m, -m or None))
        self.window_px = window
        self.c_dsm, self.c_dtm = self.dsm[crop], dtm[crop]
        self.c_valid, self.c_soil = valid[crop], soil[crop]
        self.c_height = height[crop]
        self.soil_pct = mm.soil_percent(self.c_soil, self.c_valid)
        return self


# ---------------------------------------------------------------------------
# Widgets
# ---------------------------------------------------------------------------
class ImageView(QWidget):
    """Image scaled to fit (aspect kept), optional overlay on the same rectangle, title above."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.image = None
        self.overlay = None
        self.setMinimumSize(160, 160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, image, overlay=None):
        self.image, self.overlay = image, overlay
        self.update()

    def image_rect(self):
        top = self.fontMetrics().height() + 4
        if self.image is None:
            return QRectF(0, top, self.width(), max(self.height() - top, 1))
        w, h = self.image.width(), self.image.height()
        scale = min(self.width() / w, (self.height() - top) / h)
        dw, dh = w * scale, h * scale
        return QRectF((self.width() - dw) / 2, top + (self.height() - top - dh) / 2, dw, dh)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawText(0, self.fontMetrics().ascent(), self.title)
        if self.image is not None:
            r = self.image_rect()
            p.drawImage(r, self.image)
            if self.overlay is not None:
                p.drawImage(r, self.overlay)
        self.paint_extra(p)
        p.end()

    def paint_extra(self, painter):
        pass


class MapView(ImageView):
    """
    ImageView in map coordinates: ``extent`` maps the image. A click emits its map
    coordinates; a drag emits the map offset (pan); the mouse wheel emits +1 or -1 (zoom).
    """

    clicked = pyqtSignal(float, float)
    panned = pyqtSignal(float, float)
    wheeled = pyqtSignal(int)
    DRAG_PIXELS = 5

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.extent = None
        self._press = None
        self.setCursor(Qt.CursorShape.CrossCursor)

    def to_widget(self, x, y):
        r = self.image_rect()
        xmin, ymin, xmax, ymax = self.extent
        return QPointF(r.left() + (x - xmin) / (xmax - xmin) * r.width(),
                       r.top() + (ymax - y) / (ymax - ymin) * r.height())

    @staticmethod
    def _pos(event):
        return event.position() if hasattr(event, "position") else event.localPos()

    def to_map(self, pos):
        r = self.image_rect()
        xmin, ymin, xmax, ymax = self.extent
        return (xmin + (pos.x() - r.left()) / r.width() * (xmax - xmin),
                ymax - (pos.y() - r.top()) / r.height() * (ymax - ymin))

    def mousePressEvent(self, event):
        if self.image is None or self.extent is None:
            return
        pos = self._pos(event)
        self._press = QPointF(pos) if self.image_rect().contains(pos) else None

    def mouseMoveEvent(self, event):
        if self._press is not None:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        start, self._press = self._press, None
        self.setCursor(Qt.CursorShape.CrossCursor)
        if start is None or self.extent is None:
            return
        end = self._pos(event)
        if (end - start).manhattanLength() <= self.DRAG_PIXELS:
            self.clicked.emit(*self.to_map(start))
        else:
            (x0, y0), (x1, y1) = self.to_map(start), self.to_map(end)
            self.panned.emit(x1 - x0, y1 - y0)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self.wheeled.emit(1 if delta > 0 else -1)


class OverviewMap(MapView):
    """Miniature of the whole DSM with the window as a red square."""

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.window = None
        self.setMinimumSize(140, 140)

    def paint_extra(self, p):
        if self.image is None or self.extent is None or self.window is None:
            return
        p.setPen(QPen(QColor(220, 30, 30), 2))
        a = self.to_widget(self.window[0], self.window[3])
        b = self.to_widget(self.window[2], self.window[1])
        p.drawRect(QRectF(a, b))


class MeasureView(MapView):
    """Window image where two clicks measure a distance; detected rows drawn as lines."""

    measured = pyqtSignal(float)

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.points = []
        self.rows = []          # [((x0, y0), (x1, y1))] in map coordinates
        self.clicked.connect(self.add_point)

    def clear(self):
        self.points, self.rows = [], []
        self.update()

    def add_point(self, x, y):
        if len(self.points) >= 2:
            self.points = []
        self.points.append((x, y))
        self.update()
        if len(self.points) == 2:
            (x0, y0), (x1, y1) = self.points
            self.measured.emit(math.hypot(x1 - x0, y1 - y0))

    def paint_extra(self, p):
        if self.image is None or self.extent is None:
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setClipRect(self.image_rect())
        p.setPen(QPen(QColor(255, 200, 0), 1.5, Qt.PenStyle.DashLine))
        for a, b in self.rows:
            p.drawLine(self.to_widget(*a), self.to_widget(*b))
        p.setPen(QPen(QColor(230, 20, 20), 2))
        pts = [self.to_widget(x, y) for x, y in self.points]
        if len(pts) == 2:
            p.drawLine(pts[0], pts[1])
        for q in pts:
            p.drawEllipse(q, 4, 4)


class ProfileView(QWidget):
    """DSM and DTM along a line across the rows: shows how the DTM passes under the plants."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dsm = self.dtm = None
        self.setMinimumHeight(110)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_profile(self, distance, dsm, dtm):
        self.distance, self.dsm, self.dtm = distance, dsm, dtm
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = self.fontMetrics()
        p.drawText(0, fm.ascent(), tr("mdt_w2_profile"))
        ok = None if self.dsm is None else np.isfinite(self.dsm) & np.isfinite(self.dtm)
        if ok is None or ok.sum() < 2:
            p.end()
            return
        top, left, bottom = fm.height() + 4, 46, self.height() - fm.height() - 4
        right = self.width() - 8
        lo = float(np.nanmin(self.dtm[ok])) - 0.1
        hi = float(np.nanmax(self.dsm[ok])) + 0.1
        d = self.distance

        def pt(i, v):
            return QPointF(left + (d[i] - d[0]) / (d[-1] - d[0]) * (right - left),
                           bottom - (v - lo) / (hi - lo) * (bottom - top))

        p.setPen(QPen(QColor(150, 150, 150), 1))
        p.drawLine(QPointF(left, bottom), QPointF(right, bottom))
        p.drawText(0, int(top + fm.ascent()), fmt(hi, 1))
        p.drawText(0, int(bottom), fmt(lo, 1))
        length = f"{fmt(d[-1] - d[0], 0)} m"
        p.drawText(int(right - fm.horizontalAdvance(length)), int(self.height() - 2), length)
        x = left + 10
        for values, color, label in ((self.dsm, QColor(40, 120, 40), tr("mdt_w2_profile_dsm")),
                                     (self.dtm, QColor(150, 90, 40), tr("mdt_w2_profile_dtm"))):
            path = QPainterPath()
            started = False
            for i in range(len(values)):
                if not ok[i]:
                    started = False
                    continue
                q = pt(i, values[i])
                if started:
                    path.lineTo(q)
                else:
                    path.moveTo(q)
                    started = True
            p.setPen(QPen(color, 2))
            p.drawPath(path)
            p.drawLine(QPointF(x, top + 6), QPointF(x + 18, top + 6))
            p.drawText(int(x + 22), int(top + 6 + fm.ascent() / 2), label)
            x += 40 + fm.horizontalAdvance(label)
        p.end()


class ZoomBar(QWidget):
    """Zoom buttons (+ and -) with the current window side (2.2.1)."""

    zoom = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.button_out = QToolButton()
        self.button_out.setText("\u2212")
        self.button_out.setToolTip(tr("mdt_w_zoom_out"))
        self.button_in = QToolButton()
        self.button_in.setText("+")
        self.button_in.setToolTip(tr("mdt_w_zoom_in"))
        self.label = QLabel()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(tr("mdt_w_zoom")))
        lay.addWidget(self.button_out)
        lay.addWidget(self.button_in)
        lay.addWidget(self.label)
        lay.addStretch()
        self.button_in.clicked.connect(lambda: self.zoom.emit(1))
        self.button_out.clicked.connect(lambda: self.zoom.emit(-1))

    def set_level(self, level):
        self.button_out.setEnabled(level > 0)
        self.button_in.setEnabled(level < len(ZOOM_SIDES) - 1)
        self.label.setText(tr("mdt_w_zoom_side", side=fmt(ZOOM_SIDES[level], 2 if level == 3 else 1 if level == 2 else 0)))


class ZoomMixin:
    """Zoom (buttons and wheel) and pan (drag) shared by steps 1 to 3 (2.2.1)."""

    def connect_zoom(self, views):
        self.zoom_bar.zoom.connect(self.on_zoom)
        for v in views:
            v.wheeled.connect(self.on_zoom)
            v.panned.connect(self.on_pan)

    def on_zoom(self, delta):
        w = self.wizard()
        level = min(max(w.zoom + delta, 0), len(ZOOM_SIDES) - 1)
        self.zoom_bar.set_level(level)
        if level != w.zoom and w.source is not None:
            w.zoom = level
            self.move_window(*w.centre)

    def on_pan(self, dx, dy):
        w = self.wizard()
        if w.source is not None:
            self.move_window(w.centre[0] - dx, w.centre[1] - dy)


def make_slider(lo, hi, step):
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(int(round(lo / step)), int(round(hi / step)))
    s.setTickPosition(QSlider.TickPosition.TicksBelow)
    s.setPageStep(5)
    s.setMinimumWidth(120)
    return s


def wrap_label(text=""):
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setTextFormat(Qt.TextFormat.RichText)
    return lab


def scrollable(page, layout):
    """
    Put the page content in a scroll area. Regression 2.2.0: the content imposed a large
    minimum height, so on a small or second monitor the wizard could not shrink and the
    Back, Next and Cancel buttons were pushed off the window.
    """
    inner = QWidget()
    inner.setLayout(layout)
    area = QScrollArea()
    area.setWidget(inner)
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    outer = QVBoxLayout(page)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.addWidget(area)
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page.scroll_area = area
    return area


def click_hint():
    return wrap_label(tr("mdt_w_click_overview"))


def show_overview(view, wizard):
    img, ext, _c = wizard.source.overview()
    view.extent = ext
    view.set_image(rgb_image(img))


# ---------------------------------------------------------------------------
# Step 1: DSM, RGB, resolution and row spacing
# ---------------------------------------------------------------------------
class DsmPage(ZoomMixin, QWizardPage):
    help_key = "mdt_help_page1"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w1_title"))
        self.setSubTitle(tr("mdt_w1_subtitle"))
        self.combo_dsm = QgsMapLayerComboBox()
        self.combo_dsm.setFilters(LAYER_FILTER_RASTER)
        self.combo_rgb = QgsMapLayerComboBox()
        self.combo_rgb.setFilters(LAYER_FILTER_RASTER)
        self.combo_rgb.setAllowEmptyLayer(True)
        self.combo_rgb.setLayer(None)
        self.spin_res = QDoubleSpinBox()
        self.spin_res.setRange(0.005, 5.0)
        self.spin_res.setDecimals(3)
        self.spin_res.setSingleStep(0.01)
        self.spin_res.setSuffix(" m")
        self.check_zero = QCheckBox(tr("mdt_p_zero"))
        self.check_zero.setChecked(True)
        self.spin_spacing = QDoubleSpinBox()
        self.spin_spacing.setRange(0.0, 20.0)
        self.spin_spacing.setDecimals(2)
        self.spin_spacing.setSingleStep(0.05)
        self.spin_spacing.setSuffix(" m")
        self.spin_spacing.setSpecialValueText(tr("mdt_w1_not_measured"))
        self.spin_n = QSpinBox()
        self.spin_n.setRange(1, 50)
        self.spin_n.setValue(5)
        self.button_detect = QPushButton(tr("mdt_w1_detect"))
        self.button_clear = QPushButton(tr("mdt_w1_clear"))
        self.label_measure = wrap_label(tr("mdt_w1_measure_hint"))
        self.label_info = wrap_label()
        self.overview = OverviewMap(tr("mdt_w1_overview"))
        self.view = MeasureView(tr("mdt_w1_view"))
        self.view.setMinimumSize(240, 240)
        self.zoom_bar = ZoomBar()

        form = QFormLayout()
        form.addRow(tr("mdt_w1_dsm"), self.combo_dsm)
        form.addRow(tr("mdt_w1_rgb"), self.combo_rgb)
        form.addRow(tr("mdt_w1_res"), self.spin_res)
        form.addRow("", self.check_zero)
        form.addRow(tr("mdt_w1_spacing"), self.spin_spacing)
        box = QGroupBox(tr("mdt_w1_measure_box"))
        g = QGridLayout(box)
        g.addWidget(QLabel(tr("mdt_w1_n")), 0, 0)
        g.addWidget(self.spin_n, 0, 1)
        g.addWidget(self.button_detect, 1, 0)
        g.addWidget(self.button_clear, 1, 1)
        g.addWidget(self.label_measure, 2, 0, 1, 2)
        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(box)
        left.addWidget(self.label_info)
        left.addWidget(self.overview, 1)
        left.addWidget(click_hint())
        right = QVBoxLayout()
        right.addWidget(self.zoom_bar)
        right.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addLayout(left, 2)
        row.addLayout(right, 3)
        scrollable(self, row)
        self.connect_zoom([self.view])

        self.combo_dsm.layerChanged.connect(self.on_dsm)
        self.combo_rgb.layerChanged.connect(self.on_rgb)
        self.check_zero.toggled.connect(self.on_dsm)
        self.spin_res.valueChanged.connect(self.update_info)
        self.spin_spacing.valueChanged.connect(self.update_info)
        self.spin_n.valueChanged.connect(self.on_n)
        self.view.measured.connect(self.on_measured)
        self.overview.clicked.connect(self.move_window)
        self.button_detect.clicked.connect(self.detect)
        self.button_clear.clicked.connect(self.clear_measure)
        self.distance = None

    def initializePage(self):
        self.zoom_bar.set_level(self.wizard().zoom)
        if self.wizard().source is None:
            self.on_dsm()

    # ---- data
    def on_dsm(self, *_args):
        w = self.wizard()
        if w is None:
            return
        layer = self.combo_dsm.currentLayer()
        self.view.clear()
        self.distance = None
        w.row_theta = None
        if layer is None or layer.crs().isGeographic():
            w.source = None
            self.overview.set_image(None)
            self.view.set_image(None)
            self.update_info()
            return
        self.spin_res.blockSignals(True)
        self.spin_res.setValue(round(layer.rasterUnitsPerPixelX(), 3))
        self.spin_res.blockSignals(False)
        try:
            w.source = WindowSource(layer, self.combo_rgb.currentLayer(), self.check_zero.isChecked())
        except QgsProcessingException as e:
            w.source = None
            self.label_info.setText(str(e))
            return
        show_overview(self.overview, w)
        self.move_window(*w.source.overview()[2])

    def on_rgb(self, *_args):
        w = self.wizard()
        if w is None or w.source is None:
            return
        centre = w.centre
        w.source = WindowSource(self.combo_dsm.currentLayer(), self.combo_rgb.currentLayer(),
                                self.check_zero.isChecked())
        show_overview(self.overview, w)
        self.move_window(*centre)

    def move_window(self, x, y):
        w = self.wizard()
        if w.source is None:
            return
        w.centre = (x, y)
        bounds = window_bounds(w.centre, w.window_side)
        self.overview.window = bounds
        self.overview.update()
        n = int(round(w.window_side / display_res(w.source.native, w.window_side)))
        self.view.extent = bounds
        self.view.clear()
        self.distance = None
        self.view.set_image(rgb_image(w.source.background(bounds, n, n)))
        self.update_info()

    # ---- measuring
    def on_measured(self, distance):
        self.distance = distance
        self.on_n()

    def on_n(self, *_args):
        if self.distance is None:
            return
        n = self.spin_n.value()
        self.spin_spacing.setValue(round(self.distance / n, 2))
        self.label_measure.setText(tr("mdt_w1_measured", d=fmt(self.distance, 2), n=n,
                                      s=fmt(self.distance / n, 2)))

    def clear_measure(self):
        self.distance = None
        self.view.clear()
        self.label_measure.setText(tr("mdt_w1_measure_hint"))

    def detect(self):
        w = self.wizard()
        if w.source is None:
            return
        res = max(w.source.native, 0.05)
        bounds = window_bounds(w.centre, WINDOW_SIDE)     # 30 m: several rows, whatever the zoom
        dsm = w.source.dsm_window(bounds, res, resample="average")
        gt = (bounds[0], res, 0.0, bounds[3], 0.0, -res)
        spacing, theta, score, phi = mm.detect_spacing(dsm, np.isfinite(dsm), gt)
        if spacing is None or score < 0.05:
            self.label_measure.setText(tr("mdt_w1_detect_fail"))
            return
        w.row_theta = theta
        self.distance = None
        self.view.points = []
        self.spin_spacing.setValue(round(spacing, 2))
        # row centres: u = phi + k s, with x' = x - xmin and y' = y - ymax (local coordinates)
        c, s = math.cos(theta), math.sin(theta)
        side = bounds[2] - bounds[0]
        lines = []
        for k in range(-int(2 * side / spacing) - 2, int(2 * side / spacing) + 3):
            u = phi + k * spacing
            pts = []
            for v in (-2 * side, 2 * side):          # along the row: direction (-sin, cos)
                pts.append((bounds[0] + u * c - v * s, bounds[3] + u * s + v * c))
            lines.append(tuple(pts))
        self.view.rows = lines
        self.view.update()
        az = round(math.degrees(math.atan2(-s, c))) % 180       # 179.6 shows as 0, not 180
        self.label_measure.setText(tr("mdt_w1_detected", s=fmt(spacing, 2), az=fmt(az, 0)))

    # ---- texts and validation
    def update_info(self, *_args):
        layer = self.combo_dsm.currentLayer()
        if layer is None:
            self.label_info.setText(tr("mdt_w1_no_dsm"))
            return
        crs = layer.crs()
        geo = crs.isGeographic()
        lines = [tr("mdt_w1_crs", crs=crs.authid() or "?",
                    ok=tr("mdt_w1_crs_bad") if geo else tr("mdt_w1_crs_ok"))]
        if not geo:
            ext = layer.extent()
            native = layer.rasterUnitsPerPixelX()
            res = self.spin_res.value()
            lines.append(tr("mdt_w1_native", native=fmt(native, 3),
                            area=fmt(ext.width() * ext.height() / 1e4, 2)))
            megapixels = ext.width() * ext.height() / (res * res) / 1e6
            lines.append(tr("mdt_w1_size", n=fmt(megapixels * 1e6, 0)))
            if megapixels > 150:
                lines.append(tr("mdt_w1_size_big"))
            spacing = self.spin_spacing.value()
            if spacing > 0:
                rec = mm.recommended_resolution(spacing)
                n = mm.window_pixels(spacing, mm.DEFAULT_FACTOR, res)
                lines.append(tr("mdt_w1_rec", rec=fmt(rec, 2), n=n, size=fmt(n * res, 2)))
                if res > rec:
                    lines.append(tr("mdt_w1_res_coarse"))
            if res < native * 0.99:
                lines.append(tr("mdt_w1_res_fine", native=fmt(native, 3)))
        self.label_info.setText("<br>".join(lines))

    def validatePage(self):
        w = self.wizard()
        layer = self.combo_dsm.currentLayer()
        if layer is None:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr("mdt_err_input"))
            return False
        if layer.crs().isGeographic():
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr("mdt_err_geographic", crs=layer.crs().authid()))
            return False
        spacing, res = self.spin_spacing.value(), self.spin_res.value()
        if spacing <= 0:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr("mdt_w1_err_spacing"))
            return False
        n = mm.window_pixels(spacing, FACTOR_RANGE[1], res)
        if n < mm.MIN_WINDOW:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr(
                "mdt_err_window", n=n, rec=fmt(mm.recommended_resolution(spacing), 2)))
            return False
        if w.source is None:
            return False
        w.dsm, w.rgb = layer, self.combo_rgb.currentLayer()
        w.spacing, w.resolution = spacing, res
        w.zero_nodata = self.check_zero.isChecked()
        return True


# ---------------------------------------------------------------------------
# Step 2: DTM adjustment
# ---------------------------------------------------------------------------
class DtmPage(ZoomMixin, QWizardPage):
    help_key = "mdt_help_page2"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w2_title"))
        self.setSubTitle(tr("mdt_w2_subtitle"))
        self.overview = OverviewMap(tr("mdt_w_overview"))
        self.view_dsm = MapView(tr("mdt_w2_view_dsm"))
        self.view_dtm = MapView(tr("mdt_w2_view_dtm"))
        self.zoom_bar = ZoomBar()
        self.profile = ProfileView()
        self.slider_factor = make_slider(*FACTOR_RANGE, 0.1)
        self.slider_factor.setTickInterval(5)
        self.slider_tol = make_slider(*TOL_RANGE, 0.01)
        self.slider_tol.setTickInterval(10)
        self.slider_slope = make_slider(*SLOPE_RANGE, 1)
        self.slider_slope.setTickInterval(10)
        self.slider_furrows = make_slider(*FURROW_RANGE, 0.05)
        self.slider_furrows.setTickInterval(2)
        self.combo_method = QComboBox()
        self.combo_method.addItem(tr("mdt_method_opening"), mm.METHOD_OPENING)
        self.combo_method.addItem(tr("mdt_method_slope"), mm.METHOD_SLOPE)
        self.text_method = wrap_label()
        self.labels = {k: QLabel() for k in ("factor", "tol", "slope", "furrows")}
        for lab in self.labels.values():
            lab.setMinimumWidth(80)
        self.texts = {k: wrap_label() for k in ("factor", "tol", "slope", "furrows")}
        self.label_numbers = wrap_label()

        images = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self.overview, 1)
        left.addWidget(click_hint())
        images.addLayout(left, 2)
        pair = QHBoxLayout()
        pair.addWidget(self.view_dsm)
        pair.addWidget(self.view_dtm)
        right = QVBoxLayout()
        right.addWidget(self.zoom_bar)
        right.addLayout(pair, 1)
        images.addLayout(right, 6)
        box = QGroupBox(tr("mdt_w2_controls"))
        g = QGridLayout(box)
        g.addWidget(QLabel(tr("mdt_w2_method")), 0, 0)
        g.addWidget(self.combo_method, 0, 1, 1, 2)
        g.addWidget(self.text_method, 1, 0, 1, 3)
        for i, (key, slider) in enumerate((("factor", self.slider_factor), ("tol", self.slider_tol),
                                           ("slope", self.slider_slope),
                                           ("furrows", self.slider_furrows)), start=1):
            g.addWidget(QLabel(tr(f"mdt_w2_{key}")), 2 * i, 0)
            g.addWidget(slider, 2 * i, 1)
            g.addWidget(self.labels[key], 2 * i, 2)
            g.addWidget(self.texts[key], 2 * i + 1, 0, 1, 3)
        g.setColumnStretch(1, 1)
        layout = QVBoxLayout()
        layout.addLayout(images, 3)
        layout.addWidget(self.profile, 1)
        layout.addWidget(self.label_numbers)
        layout.addWidget(box)
        scrollable(self, layout)
        self.connect_zoom([self.view_dsm, self.view_dtm])
        self.overview.clicked.connect(self.move_window)
        self.slider_factor.valueChanged.connect(self.compute)
        self.slider_tol.valueChanged.connect(self.compute)
        self.slider_slope.valueChanged.connect(self.compute)
        self.slider_furrows.valueChanged.connect(self.compute)
        self.combo_method.currentIndexChanged.connect(self.compute)

    def initializePage(self):
        w = self.wizard()
        for slider, value in ((self.slider_factor, round(w.factor / 0.1)),
                              (self.slider_tol, round(w.tolerance / 0.01)),
                              (self.slider_slope, round(w.slope)),
                              (self.slider_furrows, round(w.furrows / 0.05))):
            slider.blockSignals(True)
            slider.setValue(int(value))
            slider.blockSignals(False)
        self.combo_method.blockSignals(True)
        self.combo_method.setCurrentIndex(self.combo_method.findData(w.method))
        self.combo_method.blockSignals(False)
        self.zoom_bar.set_level(w.zoom)
        show_overview(self.overview, w)
        self.move_window(*w.centre)

    def read_sliders(self):
        w = self.wizard()
        w.factor = round(self.slider_factor.value() * 0.1, 2)
        w.tolerance = round(self.slider_tol.value() * 0.01, 2)
        w.slope = float(self.slider_slope.value())
        w.furrows = round(self.slider_furrows.value() * 0.05, 2)
        w.method = self.combo_method.currentData()

    def move_window(self, x, y):
        w = self.wizard()
        w.centre = (x, y)
        bounds = window_bounds(w.centre, w.window_side)
        self.overview.window = self.view_dsm.extent = self.view_dtm.extent = bounds
        self.overview.update()
        self.compute()

    def compute(self, *_args):
        w = self.wizard()
        self.read_sliders()
        pv = w.preview.compute(w)
        valid = pv.c_valid
        lohi = None
        if valid.any():
            hi = float(np.percentile(pv.c_dsm[valid], 98))
            lo = float(np.nanpercentile(pv.c_dtm, 2)) if np.isfinite(pv.c_dtm).any() else hi - 1
            lohi = (lo, hi)
        self.view_dsm.set_image(rgb_image(gray_relief(pv.c_dsm, valid, lohi)))
        self.view_dtm.set_image(rgb_image(gray_relief(pv.c_dtm, np.isfinite(pv.c_dtm), lohi)))
        self.update_profile(pv)
        self.update_texts(pv)

    def update_profile(self, pv):
        """Profile through the window centre, across the rows (or west to east if unknown)."""
        w = self.wizard()
        theta = w.row_theta if w.row_theta is not None else 0.0
        n = pv.c_dsm.shape[0]
        res = w.resolution
        half = n * res / 2
        t = np.arange(-half, half, res / 2)
        cols = np.clip(((half + t * math.cos(theta)) / res).astype(int), 0, n - 1)
        rows = np.clip(((half - t * math.sin(theta)) / res).astype(int), 0, n - 1)
        self.profile.set_profile(t + half, pv.c_dsm[rows, cols], pv.c_dtm[rows, cols])

    def update_texts(self, pv):
        w = self.wizard()
        self.labels["factor"].setText(f"{fmt(w.factor, 1)} x")
        self.labels["tol"].setText(f"{fmt(w.tolerance, 2)} m")
        slope_method = w.method == mm.METHOD_SLOPE
        if w.slope > 0:
            self.labels["slope"].setText(f"{fmt(w.slope, 0)}%")
        else:
            self.labels["slope"].setText(tr("mdt_w2_slope_default_short") if slope_method
                                         else tr("mdt_w2_slope_auto_short"))
        self.labels["furrows"].setText(tr("mdt_w2_furrows_off") if w.furrows <= 0
                                       else f"{fmt(w.furrows, 2)} x")
        self.text_method.setText(tr("mdt_w2_method_slope_text" if slope_method else "mdt_w2_method_opening_text"))
        if w.furrows <= 0:
            self.texts["furrows"].setText(tr("mdt_w2_furrows_text_off"))
        else:
            self.texts["furrows"].setText(tr("mdt_w2_furrows_text_low" if w.furrows < 0.35 else
                                             "mdt_w2_furrows_text_mid" if w.furrows <= 0.7 else
                                             "mdt_w2_furrows_text_high",
                                             sigma=fmt(w.furrows * w.spacing, 2)))
        self.texts["factor"].setText(tr("mdt_w2_factor_low" if w.factor < 1.3 else
                                        "mdt_w2_factor_high" if w.factor > 2.0 else "mdt_w2_factor_mid"))
        self.texts["tol"].setText(tr("mdt_w2_tol_low" if w.tolerance < 0.12 else
                                     "mdt_w2_tol_high" if w.tolerance > 0.45 else "mdt_w2_tol_mid"))
        if slope_method:
            self.texts["slope"].setText(tr("mdt_w2_slope_filter", s=fmt(pv.slope_used, 0),
                                           r=fmt(pv.window_px // 2 * w.resolution, 2)))
        else:
            self.texts["slope"].setText(tr("mdt_w2_slope_auto", s=fmt(pv.slope_used, 0)) if w.slope <= 0
                                        else tr("mdt_w2_slope_manual", s=fmt(w.slope, 0)))
        h = pv.c_height[pv.c_valid & ~pv.c_soil & np.isfinite(pv.c_height)]
        text = tr("mdt_w2_numbers", soil=fmt(pv.soil_pct, 1), n=pv.window_px,
                  size=fmt(pv.window_px * w.resolution, 2),
                  h=fmt(float(np.percentile(h, 95)), 2) if h.size > 20 else "-")
        if pv.soil_pct < mm.LOW_SOIL_PERCENT:
            text += "<br>" + tr("mdt_w2_warn_low")
        elif pv.soil_pct > mm.HIGH_SOIL_PERCENT:
            text += "<br>" + tr("mdt_w2_warn_high")
        self.label_numbers.setText(text)

    def validatePage(self):
        w = self.wizard()
        self.read_sliders()
        n = mm.window_pixels(w.spacing, w.factor, w.resolution)
        if n < mm.MIN_WINDOW:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr(
                "mdt_err_window", n=n, rec=fmt(mm.recommended_resolution(w.spacing), 2)))
            return False
        return True


# ---------------------------------------------------------------------------
# Step 3: plant mask over the image
# ---------------------------------------------------------------------------
class MaskPage(ZoomMixin, QWizardPage):
    help_key = "mdt_help_page3"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w3_title"))
        self.setSubTitle(tr("mdt_w3_subtitle"))
        self.overview = OverviewMap(tr("mdt_w_overview"))
        self.view = MapView(tr("mdt_w3_view"))
        self.view.setMinimumSize(240, 240)
        self.zoom_bar = ZoomBar()
        self.combo_mode = QComboBox()
        self.combo_mode.addItem(tr("mdt_w3_mode_fill"), False)
        self.combo_mode.addItem(tr("mdt_w3_mode_outline"), True)
        self.slider_h = make_slider(*PLANT_RANGE, 0.05)
        self.slider_h.setTickInterval(10)
        self.slider_alpha = make_slider(0, 90, 5)
        self.slider_alpha.setTickInterval(2)
        self.label_h, self.label_alpha = QLabel(), QLabel()
        for lab in (self.label_h, self.label_alpha):
            lab.setMinimumWidth(80)
        self.text_h = wrap_label()
        self.label_numbers = wrap_label()

        images = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self.overview, 1)
        left.addWidget(click_hint())
        left.addWidget(wrap_label(tr("mdt_w3_legend")))
        images.addLayout(left, 2)
        top = QHBoxLayout()
        top.addWidget(self.zoom_bar, 1)
        top.addWidget(QLabel(tr("mdt_w3_mode")))
        top.addWidget(self.combo_mode)
        right = QVBoxLayout()
        right.addLayout(top)
        right.addWidget(self.view, 1)
        images.addLayout(right, 5)
        box = QGroupBox(tr("mdt_w2_controls"))
        g = QGridLayout(box)
        g.addWidget(QLabel(tr("mdt_w3_height")), 0, 0)
        g.addWidget(self.slider_h, 0, 1)
        g.addWidget(self.label_h, 0, 2)
        g.addWidget(self.text_h, 1, 0, 1, 3)
        g.addWidget(QLabel(tr("mdt_w3_alpha")), 2, 0)
        g.addWidget(self.slider_alpha, 2, 1)
        g.addWidget(self.label_alpha, 2, 2)
        g.setColumnStretch(1, 1)
        layout = QVBoxLayout()
        layout.addLayout(images, 1)
        layout.addWidget(self.label_numbers)
        layout.addWidget(box)
        scrollable(self, layout)
        self.connect_zoom([self.view])
        self.combo_mode.currentIndexChanged.connect(self.update_mask)
        self.overview.clicked.connect(self.move_window)
        self.slider_h.valueChanged.connect(self.update_mask)
        self.slider_alpha.valueChanged.connect(self.update_mask)
        self._bg_key = None

    def initializePage(self):
        w = self.wizard()
        for slider, value in ((self.slider_h, round(w.plant_height / 0.05)),
                              (self.slider_alpha, round(w.alpha / 5))):
            slider.blockSignals(True)
            slider.setValue(int(value))
            slider.blockSignals(False)
        self.combo_mode.blockSignals(True)
        self.combo_mode.setCurrentIndex(1 if w.mask_outline else 0)
        self.combo_mode.blockSignals(False)
        self.zoom_bar.set_level(w.zoom)
        show_overview(self.overview, w)
        self.move_window(*w.centre)

    def move_window(self, x, y):
        w = self.wizard()
        w.centre = (x, y)
        self.overview.window = self.view.extent = window_bounds(w.centre, w.window_side)
        self.overview.update()
        self.update_mask()

    def update_mask(self, *_args):
        w = self.wizard()
        w.plant_height = round(self.slider_h.value() * 0.05, 2)
        w.alpha = self.slider_alpha.value() * 5
        pv = w.preview.compute(w)
        w.mask_outline = bool(self.combo_mode.currentData())
        key = (w.centre, id(w.source), w.window_side)
        if key != self._bg_key:
            self._bg_key = key
            n = int(round(w.window_side / display_res(w.source.native, w.window_side)))
            self.background = rgb_image(w.source.background(window_bounds(w.centre, w.window_side), n, n))
        plants = mm.plant_mask(pv.c_height, pv.c_valid, w.plant_height)
        self.view.set_image(self.background, rgba_image(
            mask_overlay(plants, pv.c_valid, w.alpha, outline=w.mask_outline)))
        self.label_h.setText(f"{fmt(w.plant_height, 2)} m")
        self.label_alpha.setText(f"{w.alpha}%")
        heights = pv.c_height[pv.c_valid & np.isfinite(pv.c_height)]
        top = float(np.percentile(heights, 99)) if heights.size else 0.0
        self.text_h.setText(tr("mdt_w3_height_low" if w.plant_height < 0.15 else
                               "mdt_w3_height_high" if w.plant_height > 0.6 * max(top, 0.1) else
                               "mdt_w3_height_mid"))
        _labels, patches = mm.plant_patches(plants, pv.c_height, w.resolution)
        cover = 100.0 * plants.sum() / max(int(pv.c_valid.sum()), 1)
        hp = pv.c_height[plants]
        self.label_numbers.setText(tr(
            "mdt_w3_numbers", cover=fmt(cover, 1), n=fmt(len(patches)),
            h=fmt(float(hp.mean()), 2) if hp.size else "-"))


# ---------------------------------------------------------------------------
# Step 4: outputs
# ---------------------------------------------------------------------------
class OutputPage(QWizardPage):
    help_key = "mdt_help_page4"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w4_title"))
        self.setSubTitle(tr("mdt_w4_subtitle"))
        self.checks, self.files = {}, {}
        box = QGroupBox(tr("mdt_w4_outputs"))
        g = QGridLayout(box)
        for i, (key, label, _suffix, filt) in enumerate(OUTPUTS):
            check = QCheckBox(tr(label))
            check.setChecked(True)
            fw = QgsFileWidget()
            fw.setStorageMode(QgsFileWidget.StorageMode.SaveFile)
            fw.setFilter(filt)
            fw.setDialogTitle(tr(label))
            check.toggled.connect(fw.setEnabled)
            g.addWidget(check, i, 0)
            g.addWidget(fw, i, 1)
            self.checks[key], self.files[key] = check, fw
        g.setColumnStretch(1, 1)
        self.label_folder = wrap_label()
        self.label_folder.setEnabled(False)
        self.summary = QTextBrowser()
        self.summary.setMinimumHeight(120)
        layout = QVBoxLayout()
        layout.addWidget(box)
        layout.addWidget(self.label_folder)
        layout.addWidget(QLabel(tr("mdt_w4_summary_title")))
        layout.addWidget(self.summary, 1)
        scrollable(self, layout)
        self.setFinalPage(True)
        self._dsm_id = None

    def initializePage(self):
        w = self.wizard()
        if w.dsm.id() != self._dsm_id:
            self._dsm_id = w.dsm.id()
            home = QgsProject.instance().homePath()
            last = QgsSettings().value(LAST_FOLDER_KEY, "")
            if home and os.path.isdir(home):
                folder, hint = home, "mdt_w4_from_project"
            elif last and os.path.isdir(last):
                folder, hint = last, "mdt_w4_from_last"
            else:
                folder, hint = "", "mdt_w4_no_folder"
            self.label_folder.setText(tr(hint))
            for key, path in default_outputs(w.dsm.name(), folder).items():
                self.files[key].setFilePath(path)
        rgb = w.rgb.name() if w.rgb is not None else tr("mdt_w4_no_rgb")
        self.summary.setHtml(tr(
            "mdt_w4_summary", dsm=w.dsm.name(), crs=w.dsm.crs().authid(), rgb=rgb,
            res=fmt(w.resolution, 3), spacing=fmt(w.spacing, 2), factor=fmt(w.factor, 1),
            window=fmt(mm.window_pixels(w.spacing, w.factor, w.resolution) * w.resolution, 2),
            tol=fmt(w.tolerance, 2),
            slope=(f"{fmt(w.slope, 0)}%" if w.slope > 0 else
                   tr("mdt_w2_slope_default_short") if w.method == mm.METHOD_SLOPE else tr("mdt_w2_slope_auto_short")),
            method=tr("mdt_method_slope" if w.method == mm.METHOD_SLOPE else "mdt_method_opening"),
            furrows=tr("mdt_w2_furrows_off") if w.furrows <= 0 else
            tr("mdt_w4_furrows_on", f=fmt(w.furrows, 2), sigma=fmt(w.furrows * w.spacing, 2)),
            h=fmt(w.plant_height, 2)))

    def chosen(self):
        return {key: self.files[key].filePath().strip() for key, *_ in OUTPUTS
                if self.checks[key].isChecked()}

    def validatePage(self):
        chosen = self.chosen()
        if not chosen:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr("mdt_w4_err_none"))
            return False
        for key in list(chosen):
            path = chosen[key]
            if not path:
                QMessageBox.warning(self, tr("mdt_wizard_title"), tr("mdt_w4_err_path"))
                return False
            ext = ".shp" if key == "OUT_POLYGONS" else ".tif"
            if not path.lower().endswith(ext):
                path += ext
                chosen[key] = path
            folder = os.path.dirname(path)
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError:
                folder = ""
            if not folder or not os.access(folder, os.W_OK):
                QMessageBox.warning(self, tr("mdt_wizard_title"), tr("mdt_w4_err_folder", path=path))
                return False
        w = self.wizard()
        w.outputs = chosen
        QgsSettings().setValue(LAST_FOLDER_KEY, os.path.dirname(next(iter(chosen.values()))))
        return True


# ---------------------------------------------------------------------------
# Wizard and run
# ---------------------------------------------------------------------------
class MdtWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("mdt_wizard_title"))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, True)
        self.setButtonText(QWizard.WizardButton.HelpButton, tr("help"))
        self.setButtonText(QWizard.WizardButton.NextButton, tr("next"))
        self.setButtonText(QWizard.WizardButton.BackButton, tr("back"))
        self.setButtonText(QWizard.WizardButton.FinishButton, tr("run"))
        self.setButtonText(QWizard.WizardButton.CancelButton, tr("cancel"))
        self.setMinimumSize(560, 420)
        self.resize(1140, 860)
        self.source = None
        self.preview = Preview()
        self.dsm = self.rgb = None
        self.centre = (0.0, 0.0)
        self.row_theta = None
        self.spacing = 0.0
        self.resolution = 0.25
        self.zero_nodata = True
        self.factor = mm.DEFAULT_FACTOR
        self.tolerance = DEFAULT_TOLERANCE
        self.slope = 0.0
        self.method = mm.METHOD_OPENING
        self.furrows = 0.0
        self.plant_height = mm.DEFAULT_PLANT_HEIGHT
        self.alpha = DEFAULT_ALPHA
        self.mask_outline = False
        self.zoom = 0                   # index in ZOOM_SIDES (2.2.1)
        self.outputs = {}
        for page in (DsmPage(), DtmPage(), MaskPage(), OutputPage()):
            self.addPage(page)
        self.helpRequested.connect(self.show_help)
        self._fitted = False

    @property
    def window_side(self):
        return ZOOM_SIDES[self.zoom]

    def fit_to_screen(self):
        """Size the window to the screen it is on (regression 2.2.0, see ``scrollable``)."""
        screen = self.screen() if hasattr(self, "screen") else None
        if screen is None:
            return
        avail = screen.availableGeometry()
        width = min(self.width(), int(avail.width() * 0.95))
        height = min(self.height(), int(avail.height() * 0.92))
        self.resize(max(width, self.minimumWidth()), max(height, self.minimumHeight()))
        geo = self.frameGeometry()
        geo.moveCenter(avail.center())
        self.move(geo.topLeft())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._fitted:
            self._fitted = True
            self.fit_to_screen()

    def show_help(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr("help"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(tr(getattr(self.currentPage(), "help_key", "mdt_help_page1")))
        box.exec()

    def parameters(self):
        params = {
            "INPUT": self.dsm, "CROP": mm.CUSTOM, "SPACING": self.spacing, "FACTOR": self.factor,
            "RESOLUTION": self.resolution, "TOLERANCE": self.tolerance, "SLOPE": self.slope,
            "METHOD": self.method, "FURROWS": self.furrows,
            "PLANT_HEIGHT": self.plant_height, "ZERO_NODATA": self.zero_nodata,
        }
        for key, *_ in OUTPUTS:
            params[key] = self.outputs.get(key)
        return params


class _LogFeedback(QgsProcessingFeedback):
    """Feedback that drives a progress dialog and keeps the log lines for the final message."""

    def __init__(self, dialog=None):
        super().__init__()
        self.dialog = dialog
        self.lines = []
        self.warnings = []
        self.progressChanged.connect(self._on_progress)

    def _on_progress(self, value):
        if self.dialog is not None:
            self.dialog.setValue(int(value))
            QCoreApplication.processEvents()
            if self.dialog.wasCanceled():
                self.cancel()

    def pushInfo(self, info):
        super().pushInfo(info)
        self.lines.append(info.strip())
        if self.dialog is not None:
            self.dialog.setLabelText(info.strip())
            QCoreApplication.processEvents()

    def reportError(self, error, fatalError=False):
        super().reportError(error, fatalError)
        self.warnings.append(error.strip())


def release_outputs(paths):
    """Remove from the project the layers that read these files (they would stay locked)."""
    targets = {os.path.normcase(os.path.abspath(p)) for p in paths if p}
    ids = [lyr.id() for lyr in QgsProject.instance().mapLayers().values()
           if os.path.normcase(os.path.abspath(lyr.source().split("|")[0])) in targets]
    if ids:
        QgsProject.instance().removeMapLayers(ids)


def load_mdt_results(result, wizard):
    """Load the outputs, styled, into the 'DTM and plant height' group."""
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    name = tr("mdt_group_name")
    group = root.findGroup(name) or root.insertGroup(0, name)
    base = wizard.dsm.name()
    for key, label in (("OUT_POLYGONS", "mdt_p_out_polygons"), ("OUT_MASK", "mdt_p_out_mask"),
                       ("OUT_HEIGHT", "mdt_p_out_height"), ("OUT_DTM", "mdt_p_out_dtm")):
        path = result.get(key)
        if not path:
            continue
        title = f"{base} | {tr(label)}"
        if key == "OUT_POLYGONS":
            layer = QgsVectorLayer(path, title, "ogr")
            style_plant_polygons(layer)
        else:
            layer = QgsRasterLayer(path, title)
            if not layer.isValid():
                continue
            st = layer.dataProvider().bandStatistics(1)
            if key == "OUT_MASK":
                style_plant_mask(layer)
            elif key == "OUT_HEIGHT":
                style_pseudocolor(layer, 0.0, max(min(st.maximumValue, st.mean + 2 * st.stdDev), 0.1), "Viridis")
            else:
                style_pseudocolor(layer, st.minimumValue, st.maximumValue, "Spectral", invert=True)
        if not layer.isValid():
            continue
        project.addMapLayer(layer, False)
        node = group.addLayer(layer)
        node.setItemVisibilityChecked(key in ("OUT_HEIGHT", "OUT_POLYGONS"))
    group.setExpanded(True)


def run_mdt_job(wizard, feedback):
    """Run the algorithm with the wizard choices and load the results. Returns the result dict."""
    from qgis import processing
    params = wizard.parameters()
    release_outputs([v for k, v in params.items() if k.startswith("OUT_") and v])
    context = QgsProcessingContext()
    context.setProject(QgsProject.instance())
    result = processing.run("agriprecisa:dtm_row_crops", params, context=context, feedback=feedback)
    load_mdt_results(result, wizard)
    return result


def run_wizard(iface):
    wizard = MdtWizard(iface.mainWindow())
    if wizard.exec() != QDialog.DialogCode.Accepted:
        return
    progress = QProgressDialog(tr("starting"), tr("cancel"), 0, 100, iface.mainWindow())
    progress.setWindowTitle(tr("mdt_wizard_title"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    feedback = _LogFeedback(progress)
    try:
        run_mdt_job(wizard, feedback)
    except QgsProcessingException as e:
        progress.close()
        if not feedback.isCanceled():
            QMessageBox.warning(iface.mainWindow(), tr("mdt_wizard_title"), str(e))
        return
    except Exception:
        progress.close()
        QMessageBox.critical(iface.mainWindow(), tr("error_title"), traceback.format_exc())
        return
    progress.close()
    iface.mapCanvas().refresh()
    folders = sorted({os.path.dirname(p) for p in wizard.outputs.values()})
    msg = tr("mdt_done", folder=", ".join(folders)) + "\n\n" + "\n".join(
        ln for ln in feedback.lines if not ln[:1].isdigit())
    if feedback.warnings:
        msg += "\n\n" + tr("warnings") + "\n" + "\n".join(feedback.warnings)
    QMessageBox.information(iface.mainWindow(), tr("mdt_wizard_title"), msg)
