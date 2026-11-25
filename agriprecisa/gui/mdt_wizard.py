# -*- coding: utf-8 -*-
"""
AgriPrecisa: step-by-step wizard for "DTM and plant height in row crops".

Steps: DSM and crop -> live preview of the soil mask in a window chosen on the field
(tolerance and window factor sliders) -> statistics and output folder -> summary.
The Processing algorithm agriprecisa:dtm_row_crops does the work; the wizard loads and
styles the results in the "DTM and plant height" group.
"""

import os
import traceback

import numpy as np
from qgis.PyQt.QtCore import Qt, QCoreApplication, QPointF, QRectF, pyqtSignal
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QPen
from qgis.PyQt.QtWidgets import (
    QDialog, QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel,
    QComboBox, QLineEdit, QPushButton, QFileDialog, QDoubleSpinBox, QCheckBox, QMessageBox,
    QProgressDialog, QTextBrowser, QGroupBox, QSlider, QWidget, QSizePolicy,
)
from qgis.core import (
    QgsSettings, QgsProject, QgsRasterLayer, QgsVectorLayer, QgsProcessingContext,
    QgsProcessingFeedback, QgsProcessingException,
)
from qgis.gui import QgsMapLayerComboBox

from ..core import mdt_math as mm
from ..core import mdt_stats as ms
from ..core.compat import LAYER_FILTER_RASTER
from ..core.paths import default_output_folder, prepare_output_folder
from ..i18n import tr, fmt
from ..processing_provider.alg_dtm_rows import (
    crop_name, style_pseudocolor, style_soil_mask, style_graduated_vector,
)
from .idw_wizard import add_side_panel

LAST_FOLDER_KEY = "AgriPrecisa/mdt_last_output_folder"
FOLDER_HINT = {"last": "p1_folder_from_last", "project": "p1_folder_from_project",
               "none": "p1_folder_none"}
PREVIEW_SIDE = 30.0          # metres, side of the preview window (at least 6 row spacings)
OVERVIEW_PIXELS = 320        # longest side of the field miniature
TOL_RANGE = (0.02, 1.00)     # tolerance slider (m)
FACTOR_RANGE = (1.0, 3.0)    # window factor slider
PLANT_STATS_BY_DEFAULT = ("citrus", "eucalyptus", "grapevine")
SOIL_RGB = (161, 120, 92)
PLANT_RGB = (46, 125, 50)
NODATA_RGB = (225, 225, 225)


def output_names(dsm_name):
    """File names of the outputs, prefixed with the DSM name (no characters invalid on Windows)."""
    base = "".join(c if c.isalnum() or c in "-_" else "_" for c in dsm_name).strip("_") or "MDS"
    return {"OUT_DTM": f"{base}_MDT.tif", "OUT_HEIGHT": f"{base}_Altura.tif",
            "OUT_MASK": f"{base}_Mascara_solo.tif", "OUT_ROWS": f"{base}_Trechos_linhas.shp",
            "OUT_PLANTS": f"{base}_Topos_plantas.shp", "OUT_CROWNS": f"{base}_Copas_plantas.shp"}


def rgb_image(rgb):
    """QImage (copy) from an (h, w, 3) uint8 array."""
    rgb = np.ascontiguousarray(rgb, dtype=np.uint8)
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


def gray_relief(values, valid):
    """Grey shades from low (dark) to high (light), light grey where there is no data."""
    out = np.empty(values.shape + (3,), np.uint8)
    out[:] = NODATA_RGB
    if valid.any():
        lo, hi = np.percentile(values[valid], (2, 98))
        t = np.clip((values - lo) / (hi - lo if hi > lo else 1.0), 0, 1)
        g = (40 + 200 * t).astype(np.uint8)
        out[valid] = np.stack([g[valid]] * 3, axis=-1)
    return out


def mask_rgb(soil, valid):
    out = np.empty(soil.shape + (3,), np.uint8)
    out[:] = NODATA_RGB
    out[valid & soil] = SOIL_RGB
    out[valid & ~soil] = PLANT_RGB
    return out


# ---------------------------------------------------------------------------
# Small widgets
# ---------------------------------------------------------------------------
class ImageView(QWidget):
    """An image scaled to fit, keeping the aspect ratio, with a title above it."""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.image = None
        self.setMinimumSize(200, 200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_image(self, image):
        self.image = image
        self.update()

    def image_rect(self):
        top = self.fontMetrics().height() + 4
        if self.image is None:
            return QRectF(0, top, self.width(), self.height() - top)
        w, h = self.image.width(), self.image.height()
        scale = min(self.width() / w, (self.height() - top) / h)
        dw, dh = w * scale, h * scale
        return QRectF((self.width() - dw) / 2, top + (self.height() - top - dh) / 2, dw, dh)

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawText(0, self.fontMetrics().ascent(), self.title)
        if self.image is not None:
            p.drawImage(self.image_rect(), self.image)
        p.end()


class OverviewMap(ImageView):
    """Miniature of the whole DSM; a click moves the preview window (red square)."""

    clicked = pyqtSignal(float, float)       # map coordinates

    def __init__(self, title, parent=None):
        super().__init__(title, parent)
        self.extent = None      # (xmin, ymin, xmax, ymax)
        self.window = None      # (xmin, ymin, xmax, ymax)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMinimumSize(180, 180)

    def to_widget(self, x, y):
        r = self.image_rect()
        xmin, ymin, xmax, ymax = self.extent
        return QPointF(r.left() + (x - xmin) / (xmax - xmin) * r.width(),
                       r.top() + (ymax - y) / (ymax - ymin) * r.height())

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.image is None or self.extent is None or self.window is None:
            return
        p = QPainter(self)
        p.setPen(QPen(QColor(220, 30, 30), 2))
        a = self.to_widget(self.window[0], self.window[3])
        b = self.to_widget(self.window[2], self.window[1])
        p.drawRect(QRectF(a, b))
        p.end()

    def mousePressEvent(self, event):
        if self.image is None or self.extent is None:
            return
        r = self.image_rect()
        pos = event.position() if hasattr(event, "position") else event.localPos()
        if not r.contains(pos):
            return
        xmin, ymin, xmax, ymax = self.extent
        x = xmin + (pos.x() - r.left()) / r.width() * (xmax - xmin)
        y = ymax - (pos.y() - r.top()) / r.height() * (ymax - ymin)
        self.clicked.emit(x, y)


def make_slider(lo, hi, step):
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(int(round(lo / step)), int(round(hi / step)))
    s.setTickPosition(QSlider.TickPosition.TicksBelow)
    s.setPageStep(5)
    return s


# ---------------------------------------------------------------------------
# Step 1: DSM and crop
# ---------------------------------------------------------------------------
class DsmPage(QWizardPage):
    help_key = "mdt_help_page1"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w1_title"))
        self.setSubTitle(tr("mdt_w1_subtitle"))
        self.combo_dsm = QgsMapLayerComboBox()
        self.combo_dsm.setFilters(LAYER_FILTER_RASTER)
        self.combo_crop = QComboBox()
        for i in range(len(mm.CROPS)):
            self.combo_crop.addItem(crop_name(i), i)
        self.spin_spacing = QDoubleSpinBox()
        self.spin_spacing.setRange(0.2, 20.0)
        self.spin_spacing.setDecimals(2)
        self.spin_spacing.setSingleStep(0.1)
        self.spin_spacing.setSuffix(" m")
        self.spin_res = QDoubleSpinBox()
        self.spin_res.setRange(0.01, 5.0)
        self.spin_res.setDecimals(2)
        self.spin_res.setSingleStep(0.05)
        self.spin_res.setSuffix(" m")
        self.check_zero = QCheckBox(tr("mdt_p_zero"))
        self.check_zero.setChecked(True)
        self.label_info = QLabel()
        self.label_info.setWordWrap(True)
        self.label_info.setTextFormat(Qt.TextFormat.RichText)

        form = QFormLayout()
        form.addRow(tr("mdt_w1_dsm"), self.combo_dsm)
        form.addRow(tr("mdt_w1_crop"), self.combo_crop)
        form.addRow(tr("mdt_w1_spacing"), self.spin_spacing)
        form.addRow(tr("mdt_w1_res"), self.spin_res)
        form.addRow("", self.check_zero)
        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(self.label_info)
        layout.addStretch()
        add_side_panel(self, layout, "mdt_p1_panel")

        self.combo_crop.currentIndexChanged.connect(self.apply_crop)
        self.combo_dsm.layerChanged.connect(self.update_info)
        self.spin_spacing.valueChanged.connect(self.update_info)
        self.spin_res.valueChanged.connect(self.update_info)
        self.apply_crop()

    def apply_crop(self, *_args):
        values = mm.crop_field_values(self.combo_crop.currentData())
        if values:
            self.spin_spacing.setValue(values["SPACING"])
            self.spin_res.setValue(values["RESOLUTION"])
        self.update_info()

    def update_info(self, *_args):
        layer = self.combo_dsm.currentLayer()
        if layer is None:
            self.label_info.setText(tr("mdt_w1_no_dsm"))
            return
        crs = layer.crs()
        geo = crs.isGeographic()
        native = layer.rasterUnitsPerPixelX()
        ext = layer.extent()
        area = ext.width() * ext.height() / 10000.0
        spacing, res = self.spin_spacing.value(), self.spin_res.value()
        rec = mm.recommended_resolution(spacing)
        window = mm.window_pixels(spacing, mm.DEFAULT_FACTOR, res)
        lines = [tr("mdt_w1_crs", crs=crs.authid() or "?",
                    ok=tr("mdt_w1_crs_bad") if geo else tr("mdt_w1_crs_ok"))]
        if not geo:
            lines.append(tr("mdt_w1_native", native=fmt(native, 3), area=fmt(area, 2)))
            lines.append(tr("mdt_w1_rec", rec=fmt(rec, 2), n=window,
                            size=fmt(window * res, 2)))
            if res > rec:
                lines.append(tr("mdt_w1_res_coarse"))
            if res < native * 0.99:
                lines.append(tr("mdt_w1_res_fine", native=fmt(native, 3)))
        self.label_info.setText("<br>".join(lines))

    def validatePage(self):
        layer = self.combo_dsm.currentLayer()
        if layer is None:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr("mdt_err_input"))
            return False
        if layer.crs().isGeographic():
            QMessageBox.warning(self, tr("mdt_wizard_title"),
                                tr("mdt_err_geographic", crs=layer.crs().authid()))
            return False
        window = mm.window_pixels(self.spin_spacing.value(), FACTOR_RANGE[1], self.spin_res.value())
        if window < mm.MIN_WINDOW:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr(
                "mdt_err_window", n=window, rec=fmt(mm.recommended_resolution(self.spin_spacing.value()), 2)))
            return False
        w = self.wizard()
        w.dsm = layer
        w.crop = self.combo_crop.currentData()
        w.spacing = self.spin_spacing.value()
        w.resolution = self.spin_res.value()
        w.zero_nodata = self.check_zero.isChecked()
        values = mm.crop_field_values(w.crop)
        if values and not w.tolerance_set:
            w.tolerance = values["TOLERANCE"]
        return True


# ---------------------------------------------------------------------------
# Step 2: soil mask preview
# ---------------------------------------------------------------------------
class PreviewPage(QWizardPage):
    help_key = "mdt_help_page2"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w2_title"))
        self.setSubTitle(tr("mdt_w2_subtitle"))
        self.overview = OverviewMap(tr("mdt_w2_overview"))
        self.view_dsm = ImageView(tr("mdt_w2_view_dsm"))
        self.view_mask = ImageView(tr("mdt_w2_view_mask"))
        self.overview.clicked.connect(self.move_window)

        self.slider_tol = make_slider(*TOL_RANGE, 0.01)
        self.slider_tol.setTickInterval(10)
        self.label_tol = QLabel()
        self.label_tol_text = QLabel()
        self.slider_factor = make_slider(*FACTOR_RANGE, 0.1)
        self.slider_factor.setTickInterval(5)
        self.label_factor = QLabel()
        self.label_factor_text = QLabel()
        for lab in (self.label_tol_text, self.label_factor_text):
            lab.setWordWrap(True)
            lab.setTextFormat(Qt.TextFormat.RichText)
        for lab in (self.label_tol, self.label_factor):
            lab.setMinimumWidth(70)
        self.label_numbers = QLabel()
        self.label_numbers.setWordWrap(True)
        self.label_numbers.setTextFormat(Qt.TextFormat.RichText)
        legend = QLabel(tr("mdt_w2_legend"))
        legend.setTextFormat(Qt.TextFormat.RichText)

        images = QHBoxLayout()
        left = QVBoxLayout()
        left.addWidget(self.overview, 1)
        left.addWidget(QLabel(tr("mdt_w2_click")))
        images.addLayout(left, 2)
        images.addWidget(self.view_dsm, 3)
        images.addWidget(self.view_mask, 3)

        box = QGroupBox(tr("mdt_w2_controls"))
        g = QGridLayout(box)
        g.addWidget(QLabel(tr("mdt_w2_tol")), 0, 0)
        g.addWidget(self.slider_tol, 0, 1)
        g.addWidget(self.label_tol, 0, 2)
        g.addWidget(self.label_tol_text, 1, 0, 1, 3)
        g.addWidget(QLabel(tr("mdt_w2_factor")), 2, 0)
        g.addWidget(self.slider_factor, 2, 1)
        g.addWidget(self.label_factor, 2, 2)
        g.addWidget(self.label_factor_text, 3, 0, 1, 3)
        g.setColumnStretch(1, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(images, 1)
        layout.addWidget(legend)
        layout.addWidget(self.label_numbers)
        layout.addWidget(box)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.slider_tol.valueChanged.connect(self.on_tolerance)
        self.slider_factor.valueChanged.connect(self.on_factor)
        self._src = None
        self._key = None
        self.dsm = None          # DSM of the window plus margin (NaN = no data)
        self.margin_px = 0
        self.opening = None
        self.soil = None

    # ---- data
    def initializePage(self):
        w = self.wizard()
        key = (w.dsm.id(), w.resolution, w.zero_nodata, w.spacing)
        self.slider_tol.blockSignals(True)
        self.slider_tol.setValue(int(round(w.tolerance / 0.01)))
        self.slider_tol.blockSignals(False)
        self.slider_factor.blockSignals(True)
        self.slider_factor.setValue(int(round(w.factor / 0.1)))
        self.slider_factor.blockSignals(False)
        if key != self._key:
            self._key = key
            self.load_overview()
        else:
            self.update_texts()

    def tolerance(self):
        return self.slider_tol.value() * 0.01

    def factor(self):
        return self.slider_factor.value() * 0.1

    def _open(self):
        from osgeo import gdal
        w = self.wizard()
        src = gdal.Open(w.dsm.source())
        if src is None:
            raise QgsProcessingException(tr("mdt_err_open"))
        nd = src.GetRasterBand(1).GetNoDataValue()
        if nd is None and w.zero_nodata:
            nd = 0
        return src, nd

    def load_overview(self):
        from osgeo import gdal
        w = self.wizard()
        self._src, self._nd = self._open()
        gt = self._src.GetGeoTransform()
        xs, ys = self._src.RasterXSize, self._src.RasterYSize
        xmin, ymax = gt[0], gt[3]
        xmax, ymin = xmin + xs * gt[1], ymax + ys * gt[5]
        step = max(xmax - xmin, ymax - ymin) / OVERVIEW_PIXELS
        ov = gdal.Warp("", self._src, format="MEM", xRes=step, yRes=step, resampleAlg="average",
                       srcNodata=self._nd, dstNodata=-9999)
        arr = ov.GetRasterBand(1).ReadAsArray().astype("float64")
        valid = (arr != -9999) & np.isfinite(arr)
        if w.zero_nodata:
            valid &= arr != 0
        ogt = ov.GetGeoTransform()
        self.overview.extent = (ogt[0], ogt[3] + arr.shape[0] * ogt[5],
                                ogt[0] + arr.shape[1] * ogt[1], ogt[3])
        self.overview.set_image(rgb_image(gray_relief(arr, valid)))
        # first window: centre of the data
        if valid.any():
            r, c = np.argwhere(valid).mean(axis=0)
            cx, cy = ogt[0] + (c + 0.5) * ogt[1], ogt[3] + (r + 0.5) * ogt[5]
        else:
            cx = (self.overview.extent[0] + self.overview.extent[2]) / 2
            cy = (self.overview.extent[1] + self.overview.extent[3]) / 2
        self.move_window(cx, cy)

    def window_side(self):
        return max(PREVIEW_SIDE, 6 * self.wizard().spacing)

    def move_window(self, x, y):
        """Read the window (plus a margin for the widest window) at the working resolution."""
        from osgeo import gdal
        w = self.wizard()
        half = self.window_side() / 2
        margin = w.spacing * FACTOR_RANGE[1] / 2 + w.resolution
        self.margin_px = int(round(margin / w.resolution))
        self.overview.window = (x - half, y - half, x + half, y + half)
        self.overview.update()
        ds = gdal.Warp("", self._src, format="MEM", xRes=w.resolution, yRes=w.resolution,
                       resampleAlg="min", srcNodata=self._nd, dstNodata=-9999,
                       outputBounds=(x - half - margin, y - half - margin,
                                     x + half + margin, y + half + margin))
        arr = ds.GetRasterBand(1).ReadAsArray().astype("float64")
        arr[arr == -9999] = np.nan
        if w.zero_nodata:
            arr[arr == 0] = np.nan
        self.dsm = arr
        self.opening = None
        self.compute()

    def compute(self):
        if self.dsm is None:
            return
        w = self.wizard()
        valid = np.isfinite(self.dsm)
        window = mm.window_pixels(w.spacing, self.factor(), w.resolution)
        if self.opening is None:
            self.opening = mm.ground_surface(self.dsm, valid, max(window, 3))
        self.soil = mm.classify_soil(self.dsm, self.opening, valid, self.tolerance())
        m = self.margin_px
        crop = (slice(m, -m or None), slice(m, -m or None))
        dsm_c, valid_c, soil_c = self.dsm[crop], valid[crop], self.soil[crop]
        self.view_dsm.set_image(rgb_image(gray_relief(dsm_c, valid_c)))
        self.view_mask.set_image(rgb_image(mask_rgb(soil_c, valid_c)))
        self.window_px = window
        self.soil_pct = mm.soil_percent(soil_c, valid_c)
        # rough plant height in the window (nearest-soil fill, for orientation only)
        filled = mm.fill_nearest(np.where(self.soil, self.dsm, np.nan))
        height = (self.dsm - filled)[crop]
        plants = valid_c & ~soil_c & np.isfinite(height)
        self.plant_height = float(np.percentile(height[plants], 95)) if plants.sum() > 20 else None
        self.update_texts()

    # ---- texts
    def update_texts(self):
        w = self.wizard()
        tol, factor = self.tolerance(), self.factor()
        self.label_tol.setText(f"{fmt(tol, 2)} m")
        self.label_factor.setText(f"{fmt(factor, 1)} x")
        h = getattr(self, "plant_height", None)
        if tol < 0.12:
            key = "mdt_w2_tol_low"
        elif tol > 0.45 or (h is not None and tol > 0.4 * h):
            key = "mdt_w2_tol_high"
        else:
            key = "mdt_w2_tol_mid"
        self.label_tol_text.setText(tr(key))
        if factor < 1.3:
            key = "mdt_w2_factor_low"
        elif factor > 2.0:
            key = "mdt_w2_factor_high"
        else:
            key = "mdt_w2_factor_mid"
        self.label_factor_text.setText(tr(key))
        if not hasattr(self, "soil_pct"):
            return
        window = getattr(self, "window_px", 0)
        text = tr("mdt_w2_numbers", soil=fmt(self.soil_pct, 1), n=window,
                  size=fmt(window * w.resolution, 2),
                  h=fmt(h, 2) if h is not None else "-", side=fmt(self.window_side()))
        if self.soil_pct < mm.LOW_SOIL_PERCENT:
            text += "<br>" + tr("mdt_w2_warn_low")
        elif self.soil_pct > mm.HIGH_SOIL_PERCENT:
            text += "<br>" + tr("mdt_w2_warn_high")
        self.label_numbers.setText(text)

    def on_tolerance(self, *_args):
        self.wizard().tolerance_set = True
        self.compute()

    def on_factor(self, *_args):
        self.opening = None
        self.compute()

    def validatePage(self):
        w = self.wizard()
        w.tolerance = self.tolerance()
        w.factor = self.factor()
        if mm.window_pixels(w.spacing, w.factor, w.resolution) < mm.MIN_WINDOW:
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr(
                "mdt_err_window", n=mm.window_pixels(w.spacing, w.factor, w.resolution),
                rec=fmt(mm.recommended_resolution(w.spacing), 2)))
            return False
        return True


# ---------------------------------------------------------------------------
# Step 3: statistics and outputs
# ---------------------------------------------------------------------------
class OutputPage(QWizardPage):
    help_key = "mdt_help_page3"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w3_title"))
        self.setSubTitle(tr("mdt_w3_subtitle"))
        self.box_rows = QGroupBox(tr("mdt_w3_rows"))
        self.box_rows.setCheckable(True)
        self.box_rows.setChecked(True)
        self.spin_segment = QDoubleSpinBox()
        self.spin_segment.setRange(0.5, 500)
        self.spin_segment.setDecimals(1)
        self.spin_segment.setValue(ms.DEFAULT_SEGMENT)
        self.spin_segment.setSuffix(" m")
        f1 = QFormLayout(self.box_rows)
        f1.addRow(tr("mdt_w3_segment"), self.spin_segment)

        self.box_plants = QGroupBox(tr("mdt_w3_plants"))
        self.box_plants.setCheckable(True)
        self.spin_distance = QDoubleSpinBox()
        self.spin_distance.setRange(0.05, 20)
        self.spin_distance.setDecimals(2)
        self.spin_distance.setSuffix(" m")
        self.check_crowns = QCheckBox(tr("mdt_w3_crowns"))
        self.check_crowns.setChecked(True)
        f2 = QFormLayout(self.box_plants)
        f2.addRow(tr("mdt_w3_distance"), self.spin_distance)
        f2.addRow("", self.check_crowns)

        self.edit_folder = QLineEdit()
        browse = QPushButton(tr("browse"))
        browse.clicked.connect(self.choose_folder)
        row = QHBoxLayout()
        row.addWidget(self.edit_folder)
        row.addWidget(browse)
        self.label_folder = QLabel()
        self.label_folder.setWordWrap(True)
        self.label_folder.setEnabled(False)
        self.edit_folder.textEdited.connect(lambda _t: self.label_folder.setText(""))
        self.label_files = QLabel()
        self.label_files.setWordWrap(True)
        self.label_files.setTextFormat(Qt.TextFormat.RichText)

        form = QFormLayout()
        form.addRow(tr("p1_folder"), row)
        form.addRow("", self.label_folder)
        layout = QVBoxLayout()
        layout.addWidget(self.box_rows)
        layout.addWidget(self.box_plants)
        layout.addLayout(form)
        layout.addWidget(self.label_files)
        layout.addStretch()
        add_side_panel(self, layout, "mdt_p3_panel")
        for wdg in (self.box_rows, self.box_plants, self.check_crowns):
            wdg.toggled.connect(self.update_files)
        self._crop = None

    def initializePage(self):
        w = self.wizard()
        if w.crop != self._crop:
            self._crop = w.crop
            key = mm.CROPS[w.crop][0]
            self.spin_distance.setValue(ms.plant_distance(key, w.spacing))
            self.box_plants.setChecked(key in PLANT_STATS_BY_DEFAULT)
        if not self.edit_folder.text():
            last = QgsSettings().value(LAST_FOLDER_KEY, "")
            folder, source = default_output_folder(last, QgsProject.instance().homePath())
            self.edit_folder.setText(folder)
            self.label_folder.setText(tr(FOLDER_HINT[source]))
        self.update_files()

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("mdt_w3_folder_dialog"), self.edit_folder.text())
        if folder:
            self.edit_folder.setText(folder)
            self.label_folder.setText("")

    def chosen_outputs(self):
        keys = ["OUT_DTM", "OUT_HEIGHT", "OUT_MASK"]
        if self.box_rows.isChecked():
            keys.append("OUT_ROWS")
        if self.box_plants.isChecked():
            keys.append("OUT_PLANTS")
            if self.check_crowns.isChecked():
                keys.append("OUT_CROWNS")
        return keys

    def update_files(self, *_args):
        w = self.wizard()
        if w is None or w.dsm is None:
            return
        names = output_names(w.dsm.name())
        self.label_files.setText(tr("mdt_w3_files") + "<br>" + "<br>".join(
            f"&nbsp;&nbsp;{names[k]}" for k in self.chosen_outputs()))

    def validatePage(self):
        folder = self.edit_folder.text().strip()
        if not prepare_output_folder(folder):
            QMessageBox.warning(self, tr("mdt_wizard_title"), tr("p1_err_folder"))
            return False
        QgsSettings().setValue(LAST_FOLDER_KEY, folder)
        w = self.wizard()
        w.folder = folder
        w.outputs = self.chosen_outputs()
        w.segment = self.spin_segment.value()
        w.distance = self.spin_distance.value()
        return True


# ---------------------------------------------------------------------------
# Step 4: summary
# ---------------------------------------------------------------------------
class MdtSummaryPage(QWizardPage):
    help_key = "mdt_help_page4"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("mdt_w4_title"))
        self.setSubTitle(tr("mdt_w4_subtitle"))
        self.text = QTextBrowser()
        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        self.setFinalPage(True)

    def initializePage(self):
        w = self.wizard()
        names = output_names(w.dsm.name())
        stats = []
        if "OUT_ROWS" in w.outputs:
            stats.append(tr("mdt_w4_rows", seg=fmt(w.segment, 1),
                            gap=fmt(ms.min_gap_length(w.distance, w.resolution), 2)))
        if "OUT_PLANTS" in w.outputs:
            stats.append(tr("mdt_w4_plants", d=fmt(w.distance, 2)))
        self.text.setHtml(tr(
            "mdt_w4_summary", dsm=w.dsm.name(), crs=w.dsm.crs().authid(), crop=crop_name(w.crop),
            spacing=fmt(w.spacing, 2), res=fmt(w.resolution, 2), tol=fmt(w.tolerance, 2),
            factor=fmt(w.factor, 1),
            window=fmt(mm.window_pixels(w.spacing, w.factor, w.resolution) * w.resolution, 2),
            stats="".join(f"<li>{s}</li>" for s in stats) or f"<li>{tr('mdt_w4_no_stats')}</li>",
            folder=w.folder, files="".join(f"<li>{names[k]}</li>" for k in w.outputs)))


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
        self.setMinimumSize(880, 680)
        self.resize(1140, 880)
        self.dsm = None
        self.crop = 0
        self.spacing = 3.6
        self.resolution = 0.25
        self.zero_nodata = True
        self.tolerance = 0.25
        self.tolerance_set = False      # the student moved the tolerance slider
        self.factor = mm.DEFAULT_FACTOR
        self.folder = ""
        self.outputs = []
        self.segment = ms.DEFAULT_SEGMENT
        self.distance = 0.8
        for page in (DsmPage(), PreviewPage(), OutputPage(), MdtSummaryPage()):
            self.addPage(page)
        self.helpRequested.connect(self.show_help)

    def show_help(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr("help"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(tr(getattr(self.currentPage(), "help_key", "mdt_help_page1")))
        box.exec()

    def parameters(self):
        names = output_names(self.dsm.name())
        params = {
            "INPUT": self.dsm, "CROP": self.crop, "SPACING": self.spacing, "FACTOR": self.factor,
            "RESOLUTION": self.resolution, "TOLERANCE": self.tolerance,
            "ZERO_NODATA": self.zero_nodata, "SEGMENT": self.segment,
            "PLANT_DISTANCE": self.distance,
        }
        for key in ("OUT_DTM", "OUT_HEIGHT", "OUT_MASK", "OUT_ROWS", "OUT_PLANTS", "OUT_CROWNS"):
            params[key] = os.path.join(self.folder, names[key]) if key in self.outputs else None
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
    """Load the outputs, styled, into the 'DTM and plant height' group. Returns the height layer."""
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    name = tr("mdt_group_name")
    group = root.findGroup(name) or root.insertGroup(0, name)
    base = wizard.dsm.name()
    order = [("OUT_PLANTS", "mdt_p_out_plants"), ("OUT_CROWNS", "mdt_p_out_crowns"),
             ("OUT_ROWS", "mdt_p_out_rows"), ("OUT_MASK", "mdt_p_out_mask"),
             ("OUT_HEIGHT", "mdt_p_out_height"), ("OUT_DTM", "mdt_p_out_dtm")]
    height_layer = None
    for key, label in order:
        path = result.get(key)
        if not path:
            continue
        title = f"{base} | {tr(label)}"
        if key in ("OUT_ROWS", "OUT_PLANTS", "OUT_CROWNS"):
            layer = QgsVectorLayer(path, title, "ogr")
            style_graduated_vector(layer, "alt_media" if key == "OUT_ROWS" else "alt_max",
                                   {"OUT_ROWS": "rows", "OUT_PLANTS": "points"}.get(key, "crowns"))
        else:
            layer = QgsRasterLayer(path, title)
            if key == "OUT_MASK":
                style_soil_mask(layer)
            elif key == "OUT_HEIGHT":
                style_pseudocolor(layer, 0.0, max(result.get("_height_p95", 2.0), 0.1), "Viridis")
                height_layer = layer
            else:
                stats = layer.dataProvider().bandStatistics(1) if layer.isValid() else None
                if stats is not None:
                    style_pseudocolor(layer, stats.minimumValue, stats.maximumValue, "Spectral", invert=True)
        if not layer.isValid():
            continue
        project.addMapLayer(layer, False)
        node = group.addLayer(layer)
        node.setItemVisibilityChecked(key in ("OUT_HEIGHT", "OUT_ROWS"))
    group.setExpanded(True)
    return height_layer


def run_mdt_job(wizard, feedback):
    """Run the algorithm with the wizard choices and load the results. Returns the result dict."""
    from qgis import processing
    params = wizard.parameters()
    release_outputs([v for k, v in params.items() if k.startswith("OUT_") and v])
    context = QgsProcessingContext()
    context.setProject(QgsProject.instance())
    result = processing.run("agriprecisa:dtm_row_crops", params, context=context, feedback=feedback)
    result["_height_p95"] = 2.0
    layer = QgsRasterLayer(result["OUT_HEIGHT"], "h")
    if layer.isValid():
        st = layer.dataProvider().bandStatistics(1)
        result["_height_p95"] = max(min(st.maximumValue, st.mean + 2 * st.stdDev), 0.1)
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
    msg = tr("mdt_done", folder=wizard.folder) + "\n\n" + "\n".join(
        ln for ln in feedback.lines if not ln[:1].isdigit())
    if feedback.warnings:
        msg += "\n\n" + tr("warnings") + "\n" + "\n".join(feedback.warnings)
    QMessageBox.information(iface.mainWindow(), tr("mdt_wizard_title"), msg)
