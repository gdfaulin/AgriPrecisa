# -*- coding: utf-8 -*-
"""
AgriPrecisa: wizard step 3, IDW parameters PER ATTRIBUTE.

Each attribute has its own spatial dependence and variability, so each one keeps its own
power P, maximum of neighbours and search radius. The attribute selector at the top drives
the controls and the map preview; a summary table lists P, neighbours, radius and origin
(default, cross-validation or manual) of every attribute.

Neighbours follow the usual rule of GIS interpolators: at least MIN_NEIGHBOURS samples per
pixel (beyond the radius if needed) and at most the attribute's maximum (the nearest ones).
The maximum is shown as text and chosen by the auto-fit together with P; the radius only
saves computation and sits in a collapsed "Advanced" box.

Left column: P slider, neighbours (with the share of each neighbour in a typical pixel,
Shepard 1968), advanced radius and summary table. Right column: live map preview.
"""

import numpy as np

from qgis.PyQt.QtCore import Qt, QTimer, QCoreApplication
from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QWizardPage, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QSlider,
    QDoubleSpinBox, QWidget, QGroupBox,
    QComboBox, QMessageBox, QCheckBox, QPushButton, QApplication, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView, QProgressDialog, QScrollArea, QFrame,
)
from qgis.core import QgsProject
from qgis.gui import QgsCollapsibleGroupBox

from ..core.idw_math import (
    snap_extent, sample_density, power_band, suggest_parameters, typical_pixel_neighbours,
    nearest_k_distances, share_beyond_radius, select_neighbour_distances, radius_from_knn,
    STUDENT_POWER_MIN, STUDENT_POWER_MAX, STUDENT_RADIUS_MIN, STUDENT_RADIUS_MAX,
    DEFAULT_RADIUS_MULTIPLE, CV_MIN_VALIDATION, CV_MAX_NEIGHBOURS, MIN_NEIGHBOURS,
    DEFAULT_MAX_NEIGHBOURS,
)
from ..core.pipeline import buffered, extract_points, edge_distances
from ..i18n import tr, fmt
from .widgets import PreviewMap, InfluenceBars
from .cv_dialog import CrossValidationDialog, significant_decimals

POWER_TEXT = {"low": "p3_power_low", "mid": "p3_power_mid", "high": "p3_power_high"}
RADIUS_TEXT = {"short": "p3_radius_short", "ok": "p3_radius_ok", "limits": "p3_radius_limits"}
RADIUS_LIMIT_SHARE = 5.0  # % of the field above which the radius is said to cut the maximum
ORIGIN_TEXT = {"default": "origin_default", "cv": "origin_cv", "manual": "origin_manual"}
ORIGIN_TIP = {"default": "origin_default_tip", "cv": "origin_cv_tip", "manual": "origin_manual_tip"}
SHOW_POINTS_LIMIT = 500   # above this, samples start hidden in the preview
DEFAULT_POWER = 2.0
SUM_ATTR, SUM_P, SUM_N, SUM_R, SUM_ORIGIN = 0, 1, 2, 3, 4


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
        self.state = {}           # key -> dict(power, max_n, radius, origin, coverage, typical, density, knn)
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

        # ---- top row: attribute ----------------------------------------------
        self.combo_attr = QComboBox()
        self.combo_attr.setMinimumWidth(260)
        self.combo_attr.currentIndexChanged.connect(self.on_attr_changed)
        top = QHBoxLayout()
        top.addWidget(QLabel("<b>" + tr("p3_attribute") + "</b>"))
        top.addWidget(self.combo_attr)
        top.addStretch()

        # ---- left column: power, neighbours, advanced radius and summary ------
        self.controls = self._build_student()
        box_s = self._build_summary()

        # ---- right column: map preview over the whole height -----------------
        box_m = QGroupBox(tr("p3_preview_group"))
        self.preview = PreviewMap()
        self.preview.setMinimumSize(380, 420)
        self.preview.setToolTip(tr("p3_preview_note"))
        self.check_points = QCheckBox(tr("p3_show_samples"))
        self.check_points.toggled.connect(self.preview.set_show_points)
        lm = QVBoxLayout(box_m)
        lm.addWidget(self.check_points, 0, Qt.AlignmentFlag.AlignRight)
        lm.addWidget(self.preview, 1)
        self.box_preview = box_m

        grid = QGridLayout()
        grid.addWidget(self.controls, 0, 0)
        grid.addWidget(box_s, 1, 0)
        grid.addWidget(box_m, 0, 1, 2, 1)
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        self.scroll = scroll

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

        # neighbours: chosen by the auto-fit, shown as text, with the influence bars
        box_n = QGroupBox(tr("p3_neigh_group"))
        self.label_n = QLabel()
        self.label_n.setWordWrap(True)
        self.label_n.setMinimumHeight(3 * self.fontMetrics().lineSpacing() + 4)
        self.label_n.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.label_n.linkActivated.connect(self.show_more)
        self.bars = InfluenceBars()
        self.bars.setMinimumSize(210, 150)
        self.label_bars = QLabel("<b>" + tr("p3_bars_title") + "</b>")
        self.label_bars.setWordWrap(True)
        more_w = QLabel(_link("p3_weight_more"))
        more_w.linkActivated.connect(self.show_more)
        ln = QVBoxLayout(box_n)
        ln.addWidget(self.label_n)
        ln.addWidget(self.label_bars)
        ln.addWidget(self.bars, 1)
        ln.addWidget(more_w, 0, Qt.AlignmentFlag.AlignRight)

        # advanced: search radius (only saves computation), collapsed like in QGIS tools
        box_r = QgsCollapsibleGroupBox(tr("p3_advanced_group"))
        self.label_spacing = QLabel()
        self.label_spacing.setWordWrap(True)
        self.label_spacing.setMinimumHeight(2 * self.fontMetrics().lineSpacing() + 2)
        self.slider_r = QSlider(Qt.Orientation.Horizontal)
        self.slider_r.setRange(int(STUDENT_RADIUS_MIN * 10), int(STUDENT_RADIUS_MAX * 10))
        self.slider_r.setValue(int(DEFAULT_RADIUS_MULTIPLE * 10))
        self.slider_r.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider_r.setTickInterval(10)
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
        self.label_r_gap = QLabel()
        self.label_r_gap.setWordWrap(True)
        self.label_r_gap.setStyleSheet("color: #b35900;")     # orange warning, like QGIS
        self.label_r_gap.setVisible(False)
        lr = QVBoxLayout(box_r)
        lr.addWidget(self.label_spacing)
        lr.addLayout(row)
        lr.addWidget(self.label_r_text)
        box_r.setCollapsed(True)
        self.box_advanced = box_r

        lay.addWidget(box_p)
        lay.addWidget(box_n, 1)
        lay.addWidget(box_r)
        lay.addWidget(self.label_r_gap)      # outside the box: visible even when collapsed
        self.slider_p.valueChanged.connect(self.on_student_changed)
        self.slider_r.valueChanged.connect(self.on_student_changed)
        return page

    def _build_summary(self):
        box = QGroupBox(tr("p3_summary_group"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            [tr("sum_col_attr"), tr("sum_col_p"), tr("sum_col_n"), tr("sum_col_r"),
             tr("sum_col_origin")])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(SUM_ATTR, QHeaderView.ResizeMode.Stretch)
        for c in (SUM_P, SUM_N, SUM_R, SUM_ORIGIN):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.on_table_selection)
        self.table.setMinimumHeight(4 * self.fontMetrics().lineSpacing() + 30)

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
        # pixel: at most the grid cell, starting equal to it (each cell must hold pixel centres)
        cell = getattr(w, "cell_size", None) or self.spin_px.value()
        self.spin_px.setMaximum(cell)
        if getattr(self, "_last_cell", None) != cell:
            self.spin_px.setValue(cell)
            self._last_cell = cell
        self.spin_px.setToolTip(tr("p3_pixel_tip", cell=fmt(cell, 2)))
        self.preview.set_boundary(w.boundary_geom)
        px, py = self.preview.cell_centres()
        old_state = self.state
        self.keys, self.labels, self.state = [], {}, {}
        self.points_cache, self.edge_cache, self.cv_cache = {}, {}, {}
        self.neigh_cache = {}
        self.px, self.py = px, py
        for layer, field in w.items:
            key = (layer.id(), field)
            self.keys.append(key)
            self.labels[key] = f"{field} ({layer.name()})"
            xs, ys, _ = self.points_for(key)
            # distances from each preview pixel to its 1st..32nd nearest samples: coverage,
            # minimum and maximum of neighbours are all read from this one matrix
            knn = nearest_k_distances(px, py, xs, ys, max(CV_MAX_NEIGHBOURS))
            nearest = knn[:, 0][np.isfinite(knn[:, 0])] if knn.size else np.array([])
            if nearest.size:
                typical = float(np.percentile(nearest, 50))
                cover = float(np.percentile(nearest, 95))
            else:
                typical = cover = None
            fs = getattr(w, "layer_stats", {}).get(layer.id(), {}).get("fields", {}).get(field, {})
            density = sample_density(fs.get("inside") or fs.get("used") or 0, w.area_ha)
            st = {"coverage": cover, "typical": typical, "density": density, "nearest": nearest,
                  "knn": knn, "power": DEFAULT_POWER, "max_n": DEFAULT_MAX_NEIGHBOURS,
                  "origin": "default",
                  # default radius follows the same rule as the auto-fit: it reaches the
                  # 16 neighbours in 95 % of the field and the minimum in all of it
                  "radius": (radius_from_knn(knn, DEFAULT_MAX_NEIGHBOURS, MIN_NEIGHBOURS, cover)
                             if cover else 100.0)}
            if key in old_state and old_state[key].get("coverage") == cover:
                for k in ("power", "max_n", "radius", "origin"):   # coming back from step 4
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
    def cur(self):
        return self.state.get(self.current, {})

    def power(self):
        return self.cur().get("power", DEFAULT_POWER)

    def radius(self):
        return self.cur().get("radius", 0.0)

    def max_neighbours(self):
        return self.cur().get("max_n", DEFAULT_MAX_NEIGHBOURS)

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
        self._loading = False
        self.table.blockSignals(True)
        self.table.selectRow(index)
        self.table.blockSignals(False)
        text = (tr("p3_spacing", spacing=fmt(cover), density=fmt(st.get("density"), 1))
                if cover else tr("p3_spacing_none"))
        self.label_spacing.setText(text)
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

    def update_texts(self):
        p = self.power()
        self.label_p_value.setText("<b>" + tr("p3_power_value", p=fmt(p, 1)) + "</b>")
        self.label_p_text.setText(tr(POWER_TEXT[power_band(p)]) + "  " + _link("p3_power_more"))
        origin = self.cur().get("origin", "default")
        note = tr("p3_neigh_cv") if origin == "cv" else tr("p3_neigh_default")
        self.label_n.setText(tr("p3_neigh_text", kmin=MIN_NEIGHBOURS, kmax=self.max_neighbours())
                             + " " + note + "  " + _link("p3_neigh_more"))
        if self.spacing and self.radius() > 0:
            mult = round(self.radius() / self.spacing, 1)
            self.label_r_value.setText("<b>" + tr(
                "p3_radius_value", mult=fmt(mult, 1), spacing=fmt(self.spacing),
                radius=fmt(self.radius())) + "</b>")
            band, pct = self.radius_status()
            self.label_r_text.setText(
                tr(RADIUS_TEXT[band], kmin=MIN_NEIGHBOURS, kmax=self.max_neighbours(),
                   pct=fmt(pct, 1)) + "  " + _link("p3_radius_more"))
        else:
            self.label_r_value.setText("")
            self.label_r_text.setText(_link("p3_radius_more"))
        gap = self.gap_percent()
        self.label_r_gap.setVisible(gap > 0)
        if gap > 0:
            self.label_r_gap.setText("⚠ " + tr("p3_radius_gap", pct=fmt(gap, 1), k=MIN_NEIGHBOURS))
        self.update_visuals()

    def gap_percent(self):
        """% of the field (preview pixels) where the radius reaches fewer than the minimum."""
        knn = self.cur().get("knn")
        if knn is None:
            return 0.0
        return share_beyond_radius(knn, MIN_NEIGHBOURS, self.radius())

    def radius_status(self):
        """
        ('short', %) when the radius reaches fewer than the minimum somewhere; ('limits', %)
        when it cuts the maximum in more than RADIUS_LIMIT_SHARE % of the field; else ('ok', 0).
        """
        gap = self.gap_percent()
        if gap > 0:
            return "short", gap
        knn = self.cur().get("knn")
        cut = share_beyond_radius(knn, self.max_neighbours(), self.radius()) if knn is not None else 0.0
        if cut > RADIUS_LIMIT_SHARE:
            return "limits", cut
        return "ok", 0.0

    def update_visuals(self):
        self.timer.start()

    def neighbour_distances(self):
        """Sorted distances from a typical pixel to the samples it really uses."""
        key = self.current
        if key is None:
            return np.array([])
        if key not in self.neigh_cache:
            xs, ys, _ = self.points_for(key)
            self.neigh_cache[key] = typical_pixel_neighbours(self.px, self.py, xs, ys, radius=0)
        return select_neighbour_distances(self.neigh_cache[key], self.radius(), MIN_NEIGHBOURS,
                                          self.max_neighbours())

    def refresh_table(self):
        for row, key in enumerate(self.keys):
            st = self.state[key]
            values = [self.labels[key], fmt(st["power"], 1),
                      tr("sum_n_value", kmin=MIN_NEIGHBOURS, kmax=st["max_n"]),
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

    # ------------------------------------------------------------- preview
    def refresh_preview(self):
        self.preview.compute(self.power(), self.radius(), self.max_neighbours())
        self.bars.set_data(self.neighbour_distances(), self.power())

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
                                                    pixels=(self.px, self.py))
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
            max_neighbours=res["max_neighbours"], radius=res["radius"])
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
                            kmax=res["max_neighbours"], radius=fmt(res["radius"]),
                            rmse=fmt(res["best_rmse"], significant_decimals(res["rmse"]))))
        progress.setValue(len(self.keys))
        progress.close()
        self.on_attr_changed(self.combo_attr.currentIndex())
        self.last_cv_all = lines
        QMessageBox.information(self, tr("cv_title"), tr("cv_all_done", lines="\n".join(lines)))

    def apply_cv(self, key, res, refresh=True):
        st = self.state[key]
        st["power"] = res["power"]
        st["max_n"] = int(res["max_neighbours"])
        st["radius"] = round(res["radius"], 1)
        st["origin"] = "cv"
        if refresh:
            self.on_attr_changed(self.combo_attr.currentIndex())

    # --------------------------------------------------------------- finish
    def validatePage(self):
        w = self.wizard()
        w.params = [(self.state[k]["power"], self.state[k]["radius"], self.state[k]["max_n"])
                    for k in self.keys]
        w.param_origins = [self.state[k]["origin"] for k in self.keys]
        w.pixel = self.spin_px.value()
        return True
