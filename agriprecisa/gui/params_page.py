# -*- coding: utf-8 -*-
"""
AgriPrecisa: wizard step 3, IDW parameters PER ATTRIBUTE.

Each attribute has its own spatial dependence and variability, so each one keeps its own
power P and search radius. The attribute selector at the top drives the sliders, the
weight x distance curve and the map preview; a summary table lists P, radius and origin
(default, cross-validation or manual) of every attribute.

Student mode (default, remembered): sliders P 1.0 to 3.0 (step 0.1) and radius 1x to 4x
the attribute's coverage distance, with simple explanations and "Learn more" links.
Advanced mode: free numeric fields (P above 3, radius 0 = no limit).
"""

import numpy as np

from qgis.PyQt.QtCore import Qt, QTimer, QCoreApplication
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout, QLabel, QSlider,
    QDoubleSpinBox, QRadioButton, QButtonGroup, QStackedWidget, QWidget, QGroupBox,
    QComboBox, QMessageBox, QCheckBox, QPushButton, QApplication, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QProgressDialog, QScrollArea, QFrame,
)
from qgis.core import QgsProject, QgsSettings

from ..core.idw_math import (
    snap_extent, sample_density, power_band, radius_band, coverage_distances,
    suggest_parameters, STUDENT_POWER_MIN, STUDENT_POWER_MAX, STUDENT_RADIUS_MIN,
    STUDENT_RADIUS_MAX, DEFAULT_RADIUS_MULTIPLE, CV_MIN_VALIDATION,
)
from ..core.pipeline import buffered, extract_points, edge_distances
from ..i18n import tr, fmt
from .widgets import WeightCurve, PreviewMap
from .cv_dialog import CrossValidationDialog, significant_decimals

SETTINGS_KEY = "AgriPrecisa/idw_student_mode"
POWER_TEXT = {"low": "p3_power_low", "mid": "p3_power_mid", "high": "p3_power_high"}
RADIUS_TEXT = {"short": "p3_radius_short", "ok": "p3_radius_ok", "long": "p3_radius_long"}
ORIGIN_TEXT = {"default": "origin_default", "cv": "origin_cv", "manual": "origin_manual"}
ORIGIN_TIP = {"default": "origin_default_tip", "cv": "origin_cv_tip", "manual": "origin_manual_tip"}
SHOW_POINTS_LIMIT = 500   # above this, samples start hidden in the preview
DEFAULT_POWER = 2.0
SUM_ATTR, SUM_P, SUM_R, SUM_ORIGIN = 0, 1, 2, 3


def _link(key):
    return f'<a href="{key}">{tr("learn_more")}</a>'


class ParametersPage(QWizardPage):
    help_key = "help_page3"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("p3_title"))
        self.setSubTitle(tr("p3_subtitle"))
        self.keys = []            # (layer_id, field) in the order of the wizard items
        self.labels = {}          # key -> "field (layer)"
        self.state = {}           # key -> dict(power, radius, origin, coverage, typical, density)
        self.points_cache = {}
        self.edge_cache = {}
        self.cv_cache = {}
        self.current = None
        self.last_dialog = None
        self.last_cv_all = []
        self._loading = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(150)
        self.timer.timeout.connect(self.refresh_preview)

        # ---- top row: mode and attribute --------------------------------
        self.radio_student = QRadioButton(tr("p3_mode_student"))
        self.radio_advanced = QRadioButton(tr("p3_mode_advanced"))
        self.radio_student.setToolTip(tr("p3_mode_student_tip"))
        self.radio_advanced.setToolTip(tr("p3_mode_advanced_tip"))
        group = QButtonGroup(self)
        group.addButton(self.radio_student)
        group.addButton(self.radio_advanced)
        self.combo_attr = QComboBox()
        self.combo_attr.setMinimumWidth(240)
        self.combo_attr.currentIndexChanged.connect(self.on_attr_changed)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr("p3_mode")))
        top.addWidget(self.radio_student)
        top.addWidget(self.radio_advanced)
        top.addStretch()
        top.addWidget(QLabel("<b>" + tr("p3_attribute") + "</b>"))
        top.addWidget(self.combo_attr)

        # ---- left column: power / radius (stack) and summary --------------
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_student())
        self.stack.addWidget(self._build_advanced())
        box_s = self._build_summary()

        # ---- right column: curve and preview -------------------------------
        box_c = QGroupBox(tr("p3_curve_group"))
        self.curve = WeightCurve()
        QVBoxLayout(box_c).addWidget(self.curve)
        box_m = QGroupBox(tr("p3_preview_group"))
        self.preview = PreviewMap()
        self.preview.setToolTip(tr("p3_preview_note"))
        self.check_points = QCheckBox(tr("p3_show_samples"))
        self.check_points.toggled.connect(self.preview.set_show_points)
        lm = QVBoxLayout(box_m)
        lm.addWidget(self.check_points, 0, Qt.AlignmentFlag.AlignRight)
        lm.addWidget(self.preview, 1)

        grid = QGridLayout()
        grid.addWidget(self.stack, 0, 0)
        grid.addWidget(box_s, 1, 0)
        grid.addWidget(box_c, 0, 1)
        grid.addWidget(box_m, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(1, 1)

        # ---- pixel size (all attributes) ------------------------------------
        self.spin_px = QDoubleSpinBox()
        self.spin_px.setRange(0.1, 1000)
        self.spin_px.setDecimals(2)
        self.spin_px.setValue(5.0)
        self.spin_px.setSuffix(" m")
        self.spin_px.setMaximumWidth(110)
        self.spin_px.valueChanged.connect(self.estimate)
        self.label_estimate = QLabel()
        self.label_estimate.setWordWrap(True)
        px_row = QHBoxLayout()
        px_row.addWidget(QLabel(tr("p3_pixel")))
        px_row.addWidget(self.spin_px)
        px_row.addSpacing(12)
        px_row.addWidget(self.label_estimate, 1)

        # everything inside a scroll area: on small screens a scrollbar appears instead of
        # widgets being squeezed on top of each other
        content = QWidget()
        inner = QVBoxLayout(content)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addLayout(top)
        inner.addLayout(grid, 1)
        inner.addLayout(px_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        self.scroll = scroll

        student = QgsSettings().value(SETTINGS_KEY, True, type=bool)
        (self.radio_student if student else self.radio_advanced).setChecked(True)
        self.stack.setCurrentIndex(0 if student else 1)
        self.radio_student.toggled.connect(self.on_mode_changed)

    # ------------------------------------------------------------------ build
    def _build_student(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)

        box_p = QGroupBox(tr("p3_power_group"))
        self.slider_p = QSlider(Qt.Orientation.Horizontal)
        self.slider_p.setRange(int(STUDENT_POWER_MIN * 10), int(STUDENT_POWER_MAX * 10))
        self.slider_p.setValue(20)
        self.slider_p.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_p.setTickInterval(5)
        self.slider_p.setPageStep(5)
        self.label_p_value = QLabel()
        self.label_p_text = QLabel()
        self.label_p_text.setWordWrap(True)
        self.label_p_text.setMinimumHeight(4 * self.fontMetrics().lineSpacing() + 4)
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

        box_r = QGroupBox(tr("p3_radius_group"))
        self.label_spacing = QLabel()
        self.label_spacing.setWordWrap(True)
        self.label_spacing.setMinimumHeight(2 * self.fontMetrics().lineSpacing() + 2)
        self.slider_r = QSlider(Qt.Orientation.Horizontal)
        self.slider_r.setRange(int(STUDENT_RADIUS_MIN * 10), int(STUDENT_RADIUS_MAX * 10))
        self.slider_r.setValue(int(DEFAULT_RADIUS_MULTIPLE * 10))
        self.slider_r.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_r.setTickInterval(5)
        self.slider_r.setPageStep(5)
        self.label_r_value = QLabel()
        self.label_r_text = QLabel()
        self.label_r_text.setWordWrap(True)
        self.label_r_text.setMinimumHeight(3 * self.fontMetrics().lineSpacing() + 4)
        self.label_r_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.label_r_text.linkActivated.connect(self.show_more)
        row = QHBoxLayout()
        row.addWidget(self.label_r_value)
        row.addSpacing(8)
        row.addWidget(QLabel(fmt(STUDENT_RADIUS_MIN, 0) + "×"))
        row.addWidget(self.slider_r, 1)
        row.addWidget(QLabel(fmt(STUDENT_RADIUS_MAX, 0) + "×"))
        lr = QVBoxLayout(box_r)
        lr.addWidget(self.label_spacing)
        lr.addLayout(row)
        lr.addWidget(self.label_r_text)

        lay.addWidget(box_p)
        lay.addWidget(box_r)
        self.slider_p.valueChanged.connect(self.on_student_changed)
        self.slider_r.valueChanged.connect(self.on_student_changed)
        return page

    def _build_advanced(self):
        page = QGroupBox(tr("p3_mode_advanced"))
        form = QFormLayout(page)
        self.spin_p = QDoubleSpinBox()
        self.spin_p.setRange(0.1, 10)
        self.spin_p.setSingleStep(0.5)
        self.spin_p.setValue(DEFAULT_POWER)
        self.spin_r = QDoubleSpinBox()
        self.spin_r.setRange(0, 100000)
        self.spin_r.setDecimals(1)
        self.spin_r.setValue(100)
        self.spin_r.setSuffix(" m")
        self.spin_r.setSpecialValueText(tr("no_limit"))
        self.label_adv_cover = QLabel()
        self.label_adv_cover.setWordWrap(True)
        form.addRow(tr("p3_power"), self.spin_p)
        form.addRow(tr("p3_radius"), self.spin_r)
        form.addRow(self.label_adv_cover)
        note = QLabel(tr("p3_advanced_note"))
        note.setWordWrap(True)
        form.addRow(note)
        self.spin_p.valueChanged.connect(self.on_advanced_changed)
        self.spin_r.valueChanged.connect(self.on_advanced_changed)
        return page

    def _build_summary(self):
        box = QGroupBox(tr("p3_summary_group"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [tr("sum_col_attr"), tr("sum_col_p"), tr("sum_col_r"), tr("sum_col_origin")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(SUM_ATTR, QHeaderView.ResizeMode.Stretch)
        for c in (SUM_P, SUM_R, SUM_ORIGIN):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.on_table_selection)
        self.table.setMinimumHeight(3 * self.fontMetrics().lineSpacing() + 30)

        self.button_cv_this = QPushButton(tr("cv_this"))
        self.button_cv_this.setToolTip(tr("cv_this_tip"))
        self.button_cv_this.clicked.connect(self.run_cv_this)
        self.button_cv_all = QPushButton(tr("cv_all"))
        self.button_cv_all.setToolTip(tr("cv_all_tip"))
        self.button_cv_all.clicked.connect(self.run_cv_all)
        more = QLabel(_link("cv_more"))
        more.linkActivated.connect(self.show_more)
        buttons = QHBoxLayout()
        buttons.addWidget(self.button_cv_this)
        buttons.addWidget(self.button_cv_all)
        buttons.addStretch()
        buttons.addWidget(more)

        lay = QVBoxLayout(box)
        lay.addWidget(self.table, 1)
        lay.addLayout(buttons)
        return box

    # ------------------------------------------------------------- lifecycle
    def initializePage(self):
        w = self.wizard()
        self.preview.set_boundary(w.boundary_geom)
        px, py = self.preview.cell_centres()
        old_state = self.state
        self.keys, self.labels, self.state = [], {}, {}
        self.points_cache, self.edge_cache, self.cv_cache = {}, {}, {}
        for layer, field in w.items:
            key = (layer.id(), field)
            self.keys.append(key)
            self.labels[key] = f"{field} ({layer.name()})"
            xs, ys, _ = self.points_for(key)
            typical, cover, nearest = coverage_distances(px, py, xs, ys, return_nearest=True)
            fs = getattr(w, "layer_stats", {}).get(layer.id(), {}).get("fields", {}).get(field, {})
            density = sample_density(fs.get("inside") or fs.get("used") or 0, w.area_ha)
            st = {"coverage": cover, "typical": typical, "density": density, "nearest": nearest,
                  "power": DEFAULT_POWER, "origin": "default",
                  "radius": round(DEFAULT_RADIUS_MULTIPLE * cover, 1) if cover else 100.0}
            if key in old_state and old_state[key].get("coverage") == cover:
                for k in ("power", "radius", "origin"):   # coming back from step 4
                    st[k] = old_state[key][k]
            self.state[key] = st

        self._loading = True
        self.combo_attr.clear()
        for key in self.keys:
            self.combo_attr.addItem(self.labels[key], key)
        self.table.setRowCount(len(self.keys))
        self._loading = False

        n_max = max((self.points_cache[k][2].size for k in self.keys), default=0)
        self.check_points.setChecked(n_max <= SHOW_POINTS_LIMIT)
        self.preview.set_show_points(self.check_points.isChecked())
        self.refresh_table()
        self.select_attribute(0)
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

    # --------------------------------------------------------------- values
    def is_student(self):
        return self.radio_student.isChecked()

    def cur(self):
        return self.state.get(self.current, {})

    def power(self):
        return self.cur().get("power", DEFAULT_POWER)

    def radius(self):
        return self.cur().get("radius", 0.0)

    @property
    def spacing(self):
        """Coverage distance of the current attribute."""
        return self.cur().get("coverage")

    @property
    def typical(self):
        return self.cur().get("typical")

    # ------------------------------------------------------- attribute switch
    def select_attribute(self, index):
        if 0 <= index < len(self.keys):
            if self.combo_attr.currentIndex() != index:
                self.combo_attr.setCurrentIndex(index)     # triggers on_attr_changed
            else:
                self.on_attr_changed(index)

    def on_attr_changed(self, index):
        if self._loading or not (0 <= index < len(self.keys)):
            return
        self.current = self.keys[index]
        st = self.cur()
        cover = st.get("coverage")
        self._loading = True
        self.slider_r.setEnabled(bool(cover))
        self.button_cv_this.setEnabled(bool(cover))
        self.slider_p.setValue(int(round(min(max(st["power"], STUDENT_POWER_MIN), STUDENT_POWER_MAX) * 10)))
        if cover:
            mult = STUDENT_RADIUS_MAX if st["radius"] == 0 else st["radius"] / cover
            self.slider_r.setValue(int(round(min(max(mult, STUDENT_RADIUS_MIN), STUDENT_RADIUS_MAX) * 10)))
        self.spin_p.setValue(st["power"])
        self.spin_r.setValue(st["radius"])
        self._loading = False
        self.table.blockSignals(True)
        self.table.selectRow(index)
        self.table.blockSignals(False)
        text = (tr("p3_spacing", spacing=fmt(cover), density=fmt(st.get("density"), 1))
                if cover else tr("p3_spacing_none"))
        self.label_spacing.setText(text)
        self.label_adv_cover.setText(text)
        self.preview.set_points(*self.points_for(self.current))
        self.refresh_table()
        self.update_texts()

    def on_table_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.select_attribute(rows[0].row())

    # --------------------------------------------------------------- edits
    def set_current(self, power=None, radius=None, origin="manual"):
        st = self.cur()
        if not st:
            return
        if power is not None:
            st["power"] = round(float(power), 2)
        if radius is not None:
            st["radius"] = round(float(radius), 1)
        st["origin"] = origin
        self.refresh_table()

    def on_student_changed(self, *args):
        if not self._loading and self.current is not None:
            p = self.slider_p.value() / 10.0
            r = self.slider_r.value() / 10.0 * self.spacing if self.spacing else None
            self.set_current(power=p, radius=r)
        self.update_texts()

    def on_advanced_changed(self, *args):
        if not self._loading and self.current is not None:
            self.set_current(power=self.spin_p.value(), radius=self.spin_r.value())
        self.update_texts()

    def update_texts(self):
        p = self.power()
        self.label_p_value.setText("<b>" + tr("p3_power_value", p=fmt(p, 1)) + "</b>")
        self.label_p_text.setText(tr(POWER_TEXT[power_band(p)]) + "  " + _link("p3_power_more"))
        if self.spacing and self.radius() > 0:
            # rounded like the slider, so 10,8 m / 7,23 m reads as 1,5x ("recommended")
            mult = round(self.radius() / self.spacing, 1)
            self.label_r_value.setText("<b>" + tr(
                "p3_radius_value", mult=fmt(mult, 1), spacing=fmt(self.spacing),
                radius=fmt(self.radius())) + "</b>")
            self.label_r_text.setText(tr(RADIUS_TEXT[radius_band(mult)]) + "  " + _link("p3_radius_more"))
        else:
            self.label_r_value.setText("")
            self.label_r_text.setText(_link("p3_radius_more"))
        self.update_visuals()

    def update_visuals(self):
        # reference distance for "weight = 1": half the coverage distance, so the curves for
        # P = 1, 2 and 3 are clearly different within the search radius
        d_min = max(self.spin_px.value(), (self.spacing or 100.0) / 2.0)
        self.curve.set_params(self.power(), self.radius(), self.spacing, d_min)
        self.timer.start()

    def refresh_table(self):
        for row, key in enumerate(self.keys):
            st = self.state[key]
            values = [self.labels[key], fmt(st["power"], 1),
                      tr("no_limit") if st["radius"] == 0 else fmt(st["radius"]) + " m",
                      tr(ORIGIN_TEXT[st["origin"]])]
            for col, text in enumerate(values):
                item = self.table.item(row, col)
                if item is None:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(text)
                if col != SUM_ATTR:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                font = QFont(item.font())
                font.setBold(key == self.current)
                item.setFont(font)
            self.table.item(row, SUM_ORIGIN).setToolTip(tr(ORIGIN_TIP[st["origin"]]))

    def on_mode_changed(self, student):
        if student:
            # student sliders have limits: bring every attribute inside them
            for st in self.state.values():
                st["power"] = min(max(st["power"], STUDENT_POWER_MIN), STUDENT_POWER_MAX)
                if st.get("coverage"):
                    mult = STUDENT_RADIUS_MAX if st["radius"] == 0 else st["radius"] / st["coverage"]
                    mult = min(max(mult, STUDENT_RADIUS_MIN), STUDENT_RADIUS_MAX)
                    st["radius"] = round(mult * st["coverage"], 1)
        self.stack.setCurrentIndex(0 if student else 1)
        QgsSettings().setValue(SETTINGS_KEY, bool(student))
        self.on_attr_changed(self.combo_attr.currentIndex())

    # ------------------------------------------------------------- preview
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
        self.update_visuals()

    # ------------------------------------------------------ cross-validation
    def cv_for(self, key):
        """Cross-validation result for one attribute (cached)."""
        if key not in self.cv_cache:
            st = self.state[key]
            xs, ys, zs = self.points_for(key)
            if key not in self.edge_cache:
                self.edge_cache[key] = edge_distances(self.wizard().boundary_geom, xs, ys)
            self.cv_cache[key] = suggest_parameters(xs, ys, zs, self.edge_cache[key],
                                                    st["coverage"], st["typical"],
                                                    pixel_nearest=st["nearest"])
        return self.cv_cache[key]

    def _cv_problem(self, res):
        if res is None:
            return tr("cv_reason_cover")
        if res.get("error") == "few":
            return tr("cv_few", n=res["n_val"], min=CV_MIN_VALIDATION)
        if res.get("error"):
            return tr("cv_failed")
        return None

    def run_cv_this(self):
        key = self.current
        if key is None:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            res = self.cv_for(key)
        finally:
            QApplication.restoreOverrideCursor()
        problem = self._cv_problem(res)
        if problem:
            QMessageBox.warning(self, tr("cv_title"), problem)
            return
        dlg = CrossValidationDialog(
            self, attribute=self.labels[key], rmse=res["rmse"], coverage=res["coverage"],
            spacing=self.state[key]["coverage"], best=res["best"], best_power=res["power"],
            n_val=res["n_val"], exclusion=res["exclusion"], mean=res["mean"],
            map_coverage=res["map_coverage"])
        dlg.linkActivated.connect(self.show_more)
        self.last_dialog = dlg
        if dlg.exec():
            self.apply_cv(key, res)

    def run_cv_all(self):
        progress = QProgressDialog(tr("starting"), tr("cancel"), 0, len(self.keys), self)
        progress.setWindowTitle(tr("cv_title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        lines = []
        for i, key in enumerate(self.keys):
            if progress.wasCanceled():
                break
            progress.setLabelText(tr("cv_all_progress", label=self.labels[key]))
            progress.setValue(i)
            QCoreApplication.processEvents()
            res = self.cv_for(key)
            problem = self._cv_problem(res)
            if problem:
                lines.append(tr("cv_all_fail_line", label=self.labels[key], reason=problem))
                continue
            self.apply_cv(key, res, refresh=False)
            lines.append(tr("cv_all_line", label=self.labels[key], p=fmt(res["power"], 1),
                            mult=fmt(res["multiple"], 1), radius=fmt(res["radius"]),
                            rmse=fmt(res["best_rmse"], significant_decimals(res["rmse"]))))
        progress.setValue(len(self.keys))
        progress.close()
        self.on_attr_changed(self.combo_attr.currentIndex())
        self.last_cv_all = lines
        QMessageBox.information(self, tr("cv_title"), tr("cv_all_done", lines="\n".join(lines)))

    def apply_cv(self, key, res, refresh=True):
        st = self.state[key]
        st["power"] = res["power"]
        st["radius"] = round(res["radius"], 1)
        st["origin"] = "cv"
        if refresh:
            self.on_attr_changed(self.combo_attr.currentIndex())

    # --------------------------------------------------------------- finish
    def validatePage(self):
        w = self.wizard()
        w.params = [(self.state[k]["power"], self.state[k]["radius"]) for k in self.keys]
        w.param_origins = [self.state[k]["origin"] for k in self.keys]
        w.pixel = self.spin_px.value()
        return True
