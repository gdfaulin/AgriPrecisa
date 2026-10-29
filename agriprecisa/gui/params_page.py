# -*- coding: utf-8 -*-
"""
AgriPrecisa: wizard step 3, IDW parameters.

Student mode (default): sliders for the power P (1.0 to 3.0, step 0.1) and for the
search radius (1x to 4x the mean sample spacing), simple explanations that change with
the slider, "Learn more" links, the weight x distance curve and a live map preview.
Advanced mode: free numeric fields, including P above 3 and radius without limit.
The chosen mode is remembered between runs.
"""

from qgis.PyQt.QtCore import Qt, QTimer
import numpy as np

from qgis.PyQt.QtWidgets import (
    QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel, QSlider,
    QDoubleSpinBox, QRadioButton, QButtonGroup, QStackedWidget, QWidget, QGroupBox,
    QComboBox, QMessageBox, QCheckBox, QPushButton, QApplication,
)
from qgis.core import QgsProject, QgsSettings, QgsGeometry, QgsPointXY

from ..core.idw_math import (
    snap_extent, sample_density, power_band, radius_band, coverage_distances,
    select_validation_samples, cross_validate_idw, best_combination,
    STUDENT_POWER_MIN, STUDENT_POWER_MAX, STUDENT_RADIUS_MIN, STUDENT_RADIUS_MAX,
    DEFAULT_RADIUS_MULTIPLE,
)
from ..core.pipeline import buffered, extract_points
from ..i18n import tr, fmt
from .widgets import WeightCurve, PreviewMap
from .cv_dialog import CrossValidationDialog, CV_POWERS, CV_MULTIPLES, significant_decimals

SHOW_POINTS_LIMIT = 500   # above this, samples start hidden in the preview
MIN_VALIDATION = 10

SETTINGS_KEY = "AgriPrecisa/idw_student_mode"
POWER_TEXT = {"low": "p3_power_low", "mid": "p3_power_mid", "high": "p3_power_high"}
RADIUS_TEXT = {"short": "p3_radius_short", "ok": "p3_radius_ok", "long": "p3_radius_long"}


def _link(key):
    return f'<a href="{key}">{tr("learn_more")}</a>'


class ParametersPage(QWizardPage):
    help_key = "help_page3"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("p3_title"))
        self.setSubTitle(tr("p3_subtitle"))
        self.spacing = None
        self.typical = None
        self.density = None
        self.last_cv = None
        self.points_cache = {}
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.refresh_preview)

        # ---- mode selector ------------------------------------------------
        self.radio_student = QRadioButton(tr("p3_mode_student"))
        self.radio_advanced = QRadioButton(tr("p3_mode_advanced"))
        group = QButtonGroup(self)
        group.addButton(self.radio_student)
        group.addButton(self.radio_advanced)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel(tr("p3_mode")))
        mode_row.addWidget(self.radio_student)
        mode_row.addWidget(self.radio_advanced)
        mode_row.addStretch()

        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_student())
        self.stack.addWidget(self._build_advanced())

        # ---- pixel size (both modes) --------------------------------------
        self.spin_px = QDoubleSpinBox()
        self.spin_px.setRange(0.1, 1000)
        self.spin_px.setDecimals(2)
        self.spin_px.setValue(5.0)
        self.spin_px.setSuffix(" m")
        self.spin_px.setMaximumWidth(110)
        self.spin_px.valueChanged.connect(self.estimate)
        self.label_estimate = QLabel()
        self.label_estimate.setWordWrap(True)
        px_form = QHBoxLayout()
        px_form.addWidget(QLabel(tr("p3_pixel")))
        px_form.addWidget(self.spin_px)
        px_form.addSpacing(12)
        px_form.addWidget(self.label_estimate, 1)

        self.button_cv = QPushButton(tr("cv_button"))
        self.button_cv.setToolTip(tr("cv_tip"))
        self.button_cv.clicked.connect(self.run_cross_validation)
        self.label_cv = QLabel()
        self.label_cv.setWordWrap(True)
        self.label_cv.linkActivated.connect(self.show_more)
        cv_row = QHBoxLayout()
        cv_row.addWidget(self.button_cv)
        cv_row.addWidget(self.label_cv, 1)

        layout = QVBoxLayout(self)
        layout.addLayout(mode_row)
        layout.addWidget(self.stack, 1)
        layout.addLayout(cv_row)
        layout.addLayout(px_form)

        student = QgsSettings().value(SETTINGS_KEY, True, type=bool)
        (self.radio_student if student else self.radio_advanced).setChecked(True)
        self.stack.setCurrentIndex(0 if student else 1)
        self.radio_student.toggled.connect(self.on_mode_changed)

    # ------------------------------------------------------------------ build
    def _build_student(self):
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)

        # power
        box_p = QGroupBox(tr("p3_power_group"))
        self.slider_p = QSlider(Qt.Orientation.Horizontal)
        self.slider_p.setRange(int(STUDENT_POWER_MIN * 10), int(STUDENT_POWER_MAX * 10))
        self.slider_p.setValue(20)
        self.slider_p.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_p.setTickInterval(5)
        self.slider_p.setSingleStep(1)
        self.slider_p.setPageStep(5)
        self.label_p_value = QLabel()
        self.label_p_text = QLabel()
        self.label_p_text.setWordWrap(True)
        self.label_p_text.setMinimumHeight(40)
        self.label_p_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.label_p_text.linkActivated.connect(self.show_more)
        row = QHBoxLayout()
        row.addWidget(self.label_p_value)
        row.addSpacing(8)
        row.addWidget(QLabel(fmt(STUDENT_POWER_MIN, 1)))
        row.addWidget(self.slider_p, 1)
        row.addWidget(QLabel(fmt(STUDENT_POWER_MAX, 1)))
        lp = QVBoxLayout(box_p)
        lp.addLayout(row)
        lp.addWidget(self.label_p_text)

        # radius
        box_r = QGroupBox(tr("p3_radius_group"))
        self.label_spacing = QLabel()
        self.label_spacing.setWordWrap(True)
        self.slider_r = QSlider(Qt.Orientation.Horizontal)
        self.slider_r.setRange(int(STUDENT_RADIUS_MIN * 10), int(STUDENT_RADIUS_MAX * 10))
        self.slider_r.setValue(int(DEFAULT_RADIUS_MULTIPLE * 10))
        self.slider_r.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_r.setTickInterval(5)
        self.slider_r.setPageStep(5)
        self.label_r_value = QLabel()
        self.label_r_text = QLabel()
        self.label_r_text.setWordWrap(True)
        self.label_r_text.setMinimumHeight(40)
        self.label_r_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.label_r_text.linkActivated.connect(self.show_more)
        row = QHBoxLayout()
        row.addWidget(QLabel(fmt(STUDENT_RADIUS_MIN, 0) + "×"))
        row.addWidget(self.slider_r, 1)
        row.addWidget(QLabel(fmt(STUDENT_RADIUS_MAX, 0) + "×"))
        lr = QVBoxLayout(box_r)
        lr.addWidget(self.label_spacing)
        lr.addWidget(self.label_r_value)
        lr.addLayout(row)
        lr.addWidget(self.label_r_text)

        # curve
        box_c = QGroupBox(tr("p3_curve_group"))
        self.curve = WeightCurve()
        QVBoxLayout(box_c).addWidget(self.curve)

        # preview
        box_m = QGroupBox(tr("p3_preview_group"))
        self.combo_attr = QComboBox()
        self.combo_attr.currentIndexChanged.connect(self.on_attr_changed)
        self.preview = PreviewMap()
        self.preview.setToolTip(tr("p3_preview_note"))
        lm = QVBoxLayout(box_m)
        attr_row = QHBoxLayout()
        attr_row.addWidget(QLabel(tr("p3_preview_attr")))
        attr_row.addWidget(self.combo_attr, 1)
        self.check_points = QCheckBox(tr("p3_show_samples"))
        self.check_points.toggled.connect(self.preview.set_show_points)
        attr_row.addWidget(self.check_points)
        lm.addLayout(attr_row)
        lm.addWidget(self.preview, 1)

        grid.addWidget(box_p, 0, 0)
        grid.addWidget(box_r, 1, 0)
        grid.addWidget(box_c, 0, 1)
        grid.addWidget(box_m, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 1)

        self.slider_p.valueChanged.connect(self.on_student_changed)
        self.slider_r.valueChanged.connect(self.on_student_changed)
        return page

    def _build_advanced(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        self.spin_p = QDoubleSpinBox()
        self.spin_p.setRange(0.1, 10)
        self.spin_p.setSingleStep(0.5)
        self.spin_p.setValue(2.0)
        self.spin_r = QDoubleSpinBox()
        self.spin_r.setRange(0, 100000)
        self.spin_r.setDecimals(1)
        self.spin_r.setValue(100)
        self.spin_r.setSuffix(" m")
        self.spin_r.setSpecialValueText(tr("no_limit"))
        form.addRow(tr("p3_power"), self.spin_p)
        form.addRow(tr("p3_radius"), self.spin_r)
        note = QLabel(tr("p3_advanced_note"))
        note.setWordWrap(True)
        form.addRow(note)
        return page

    # ------------------------------------------------------------- lifecycle
    def initializePage(self):
        w = self.wizard()
        self.preview.set_boundary(w.boundary_geom)
        self.points_cache = {}
        self.combo_attr.blockSignals(True)
        self.combo_attr.clear()
        for layer, field in w.items:
            self.combo_attr.addItem(f"{field} ({layer.name()})", (layer.id(), field))
            self.points_for((layer.id(), field))
        self.combo_attr.blockSignals(False)

        self.compute_spacing()
        self.label_spacing.setText(
            tr("p3_spacing", spacing=fmt(self.spacing), density=fmt(self.density, 1))
            if self.spacing else tr("p3_spacing_none"))
        self.slider_r.setEnabled(self.spacing is not None)
        self.button_cv.setEnabled(self.spacing is not None)
        self.label_cv.setText(tr("cv_hint") + "  " + _link("cv_more"))

        n_max = max((self.points_cache[k][2].__len__() for k in self.points_cache), default=0)
        self.check_points.setChecked(n_max <= SHOW_POINTS_LIMIT)
        self.preview.set_show_points(self.check_points.isChecked())
        self.load_preview_points()
        self.on_student_changed()
        self.estimate()

    def points_for(self, key):
        """(xs, ys, zs) of one attribute inside the search area, cached as numpy arrays."""
        if key not in self.points_cache:
            w = self.wizard()
            layer = QgsProject.instance().mapLayer(key[0])
            rect = buffered(w.boundary_extent, w.tolerance)
            xs, ys, zs = extract_points(layer, key[1], rect, w.boundary.crs(),
                                        QgsProject.instance().transformContext())
            self.points_cache[key] = (np.asarray(xs, float), np.asarray(ys, float),
                                      np.asarray(zs, float))
        return self.points_cache[key]

    def compute_spacing(self):
        """
        Coverage distance of the sparsest selected attribute: 95 % of the field pixels are
        within this distance of a sample. Works for grids and for sensor passes.
        Also keeps the typical (median) distance, used as the cross-validation exclusion zone.
        """
        w = self.wizard()
        px, py = self.preview.cell_centres()
        self.spacing, self.typical = None, None
        for key, (xs, ys, _) in self.points_cache.items():
            typical, cover = coverage_distances(px, py, xs, ys)
            if cover is not None and (self.spacing is None or cover > self.spacing):
                self.spacing, self.typical = cover, typical
        densities = []
        for layer, field in w.items:
            fs = getattr(w, "layer_stats", {}).get(layer.id(), {}).get("fields", {}).get(field, {})
            d = sample_density(fs.get("inside") or fs.get("used") or 0, w.area_ha)
            if d:
                densities.append(d)
        self.density = min(densities) if densities else None

    # --------------------------------------------------------------- values
    def is_student(self):
        return self.radio_student.isChecked()

    def power(self):
        return self.slider_p.value() / 10.0 if self.is_student() else self.spin_p.value()

    def radius(self):
        if self.is_student() and self.spacing:
            return round(self.slider_r.value() / 10.0 * self.spacing, 1)
        return self.spin_r.value()

    # --------------------------------------------------------------- events
    def on_student_changed(self, *args):
        p = self.slider_p.value() / 10.0
        self.label_p_value.setText("<b>" + tr("p3_power_value", p=fmt(p, 1)) + "</b>")
        self.label_p_text.setText(tr(POWER_TEXT[power_band(p)]) + "  " + _link("p3_power_more"))
        if self.spacing:
            mult = self.slider_r.value() / 10.0
            self.label_r_value.setText("<b>" + tr(
                "p3_radius_value", mult=fmt(mult, 1), spacing=fmt(self.spacing),
                radius=fmt(mult * self.spacing)) + "</b>")
            self.label_r_text.setText(tr(RADIUS_TEXT[radius_band(mult)]) + "  " + _link("p3_radius_more"))
        else:
            self.label_r_value.setText("")
            self.label_r_text.setText(_link("p3_radius_more"))
        self.update_visuals()

    def update_visuals(self):
        # reference distance for "weight = 1": half the sample spacing, so the curves
        # for P = 1, 2 and 3 are clearly different within the search radius
        d_min = max(self.spin_px.value(), (self.spacing or 100.0) / 2.0)
        self.curve.set_params(self.power(), self.radius(), self.spacing, d_min)
        self.timer.start()

    def on_mode_changed(self, student):
        if student:
            p = min(max(self.spin_p.value(), STUDENT_POWER_MIN), STUDENT_POWER_MAX)
            self.slider_p.setValue(int(round(p * 10)))
            if self.spacing:
                r = self.spin_r.value()
                mult = STUDENT_RADIUS_MAX if r == 0 else r / self.spacing
                mult = min(max(mult, STUDENT_RADIUS_MIN), STUDENT_RADIUS_MAX)
                self.slider_r.setValue(int(round(mult * 10)))
        else:
            self.spin_p.setValue(self.slider_p.value() / 10.0)
            if self.spacing:
                self.spin_r.setValue(self.slider_r.value() / 10.0 * self.spacing)
        self.stack.setCurrentIndex(0 if student else 1)
        QgsSettings().setValue(SETTINGS_KEY, bool(student))
        self.on_student_changed()

    def on_attr_changed(self, *args):
        self.load_preview_points()
        self.timer.start()

    def load_preview_points(self):
        data = self.combo_attr.currentData()
        if not data:
            self.preview.set_points([], [], [])
            return
        self.preview.set_points(*self.points_for(tuple(data)))

    def refresh_preview(self):
        self.preview.compute(self.power(), self.radius())

    def show_more(self, key):
        box = QMessageBox(self)
        box.setWindowTitle(tr("learn_more"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(tr(key))
        box.exec()

    def estimate(self):
        w = self.wizard()
        if w is None or w.boundary_extent is None:
            return
        e = w.boundary_extent
        *_, ncol, nrow = snap_extent(e.xMinimum(), e.yMinimum(), e.xMaximum(), e.yMaximum(),
                                     self.spin_px.value())
        total = ncol * nrow
        text = tr("p3_estimate", ncol=fmt(ncol), nrow=fmt(nrow), total=fmt(total))
        if total > 5_000_000:
            text += "<br>" + tr("p3_big")
        self.label_estimate.setText(text)
        if hasattr(self, "curve"):
            self.update_visuals()

    # ------------------------------------------------------ cross-validation
    def edge_distances(self, xs, ys):
        """Distance of each sample to the field border; -1 for samples outside the field."""
        geom = self.wizard().boundary_geom
        engine = QgsGeometry.createGeometryEngine(geom.constGet())
        engine.prepareGeometry()
        border = QgsGeometry(geom.constGet().boundary())
        out = np.full(len(xs), -1.0)
        for k, (x, y) in enumerate(zip(xs, ys)):
            pt = QgsGeometry.fromPointXY(QgsPointXY(float(x), float(y)))
            if engine.intersects(pt.constGet()):
                out[k] = border.distance(pt)
        return out

    def run_cross_validation(self):
        data = self.combo_attr.currentData()
        if not data or not self.spacing:
            return
        xs, ys, zs = self.points_for(tuple(data))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            edge = self.edge_distances(xs, ys)
            val = select_validation_samples(xs, ys, zs, edge, n_target=60,
                                            edge_buffer=self.spacing)
            if len(val) < MIN_VALIDATION:
                QApplication.restoreOverrideCursor()
                QMessageBox.warning(self, tr("cv_title"), tr("cv_few", n=len(val), min=MIN_VALIDATION))
                return
            radii = np.array(CV_MULTIPLES) * self.spacing
            exclusion = self.typical or 0.0
            rmse, cov = cross_validate_idw(xs, ys, zs, val, CV_POWERS, radii, exclusion)
            best = best_combination(rmse, cov)
            fine_p = None
            if best is not None:
                fine = np.round(np.arange(1.0, 3.0001, 0.1), 1)
                rf, cf = cross_validate_idw(xs, ys, zs, val, fine, radii[[best[1]]], exclusion)
                k = best_combination(rf, cf)
                fine_p = float(fine[k[0]]) if k else float(CV_POWERS[best[0]])
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        if best is None:
            QMessageBox.warning(self, tr("cv_title"), tr("cv_failed"))
            return
        dlg = CrossValidationDialog(
            self, attribute=self.combo_attr.currentText(), rmse=rmse, coverage=cov,
            spacing=self.spacing, best=best, best_power=fine_p, n_val=len(val),
            exclusion=exclusion, mean=float(np.mean(zs[val])))
        dlg.linkActivated.connect(self.show_more)
        self.last_cv = dlg.result_summary
        if dlg.exec():
            self.apply_cv(fine_p, CV_MULTIPLES[best[1]])
        self.label_cv.setText(tr("cv_done", p=fmt(fine_p, 1), mult=fmt(CV_MULTIPLES[best[1]], 1),
                                 radius=fmt(CV_MULTIPLES[best[1]] * self.spacing),
                                 rmse=fmt(float(rmse[best]), significant_decimals(rmse)))
                          + "  " + _link("cv_more"))

    def apply_cv(self, power, multiple):
        if self.is_student():
            self.slider_p.setValue(int(round(min(max(power, STUDENT_POWER_MIN), STUDENT_POWER_MAX) * 10)))
            self.slider_r.setValue(int(round(min(max(multiple, STUDENT_RADIUS_MIN), STUDENT_RADIUS_MAX) * 10)))
        else:
            self.spin_p.setValue(power)
            self.spin_r.setValue(round(multiple * self.spacing, 1))
        self.on_student_changed()

    def validatePage(self):
        w = self.wizard()
        w.power = self.power()
        w.radius = self.radius()
        w.pixel = self.spin_px.value()
        return True
