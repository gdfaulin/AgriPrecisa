# -*- coding: utf-8 -*-
"""
AgriPrecisa: step-by-step wizard for the IDW vector grid tool.

Steps: boundary and output folder -> point layers and fields ->
IDW parameters -> summary. Results are loaded into the "Interpolated"
group, one styled copy per interpolated field.
"""

import datetime
import os
import traceback

from qgis.PyQt.QtCore import Qt, QCoreApplication
from qgis.PyQt.QtWidgets import (
    QDialog, QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QComboBox, QLineEdit, QPushButton, QFileDialog, QDoubleSpinBox, QCheckBox,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QProgressDialog, QTextBrowser,
)
from qgis.core import (
    QgsSettings,
    QgsApplication, QgsProject, QgsVectorLayer, QgsProcessingContext, QgsProcessingFeedback,
    QgsProcessingException, QgsProcessingFeatureSourceDefinition,
)

from ..core.compat import GEOM_POINT, GEOM_POLYGON
from ..core.pipeline import (
    IdwJob, run_idw_job, crs_in_meters, buffered, features_extent, boundary_geometry,
    sample_stats,
    style_graduated, rect_to_crs, N_CLASSES, COLOR_RAMP,
)
from ..core.idw_math import snap_extent, sample_density
from ..i18n import tr, fmt
from ..core.paths import default_output_folder, prepare_output_folder
from .params_page import ParametersPage, ORIGIN_TEXT

LAST_FOLDER_KEY = "AgriPrecisa/last_output_folder"
FOLDER_HINT = {"last": "p1_folder_from_last", "project": "p1_folder_from_project",
               "none": "p1_folder_none"}


# ---------------------------------------------------------------------------
# Page 1: boundary, tolerance and output folder
# ---------------------------------------------------------------------------
class BoundaryPage(QWizardPage):
    help_key = "help_page1"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("p1_title"))
        self.setSubTitle(tr("p1_subtitle"))

        self.combo = QComboBox()
        self.check_selected = QCheckBox(tr("p1_selected_only"))
        self.spin_tol = QDoubleSpinBox()
        self.spin_tol.setRange(0, 10000)
        self.spin_tol.setDecimals(1)
        self.spin_tol.setValue(50)
        self.spin_tol.setSuffix(" m")

        self.edit_folder = QLineEdit()
        browse = QPushButton(tr("browse"))
        browse.clicked.connect(self.choose_folder)
        row = QHBoxLayout()
        row.addWidget(self.edit_folder)
        row.addWidget(browse)
        self.label_folder = QLabel()
        self.label_folder.setWordWrap(True)
        self.label_folder.setEnabled(False)     # greyed hint, like QGIS
        self.edit_folder.textEdited.connect(lambda _t: self.label_folder.setText(""))

        self.label_crs = QLabel()
        self.label_crs.setWordWrap(True)
        self.combo.currentIndexChanged.connect(self.update_info)

        form = QFormLayout()
        form.addRow(tr("p1_boundary"), self.combo)
        form.addRow("", self.check_selected)
        form.addRow(tr("p1_tolerance"), self.spin_tol)
        form.addRow(tr("p1_folder"), row)
        form.addRow("", self.label_folder)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.label_crs)
        layout.addStretch()

    def initializePage(self):
        self.combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == GEOM_POLYGON:
                ok, tip_key = crs_status(layer.crs())
                if ok:
                    self.combo.addItem(layer_label(layer), layer.id())
                else:
                    self.combo.addItem(QgsApplication.getThemeIcon("/mIconWarning.svg"),
                                       layer_label(layer), layer.id())
                self.combo.setItemData(self.combo.count() - 1,
                                       tr(tip_key, crs=crs_code(layer.crs())),
                                       Qt.ItemDataRole.ToolTipRole)
        self.update_info()
        if not self.edit_folder.text().strip():
            self.fill_default_folder()

    def fill_default_folder(self):
        """Last folder used; otherwise <project folder>/AgriPrecisa; otherwise empty."""
        last = QgsSettings().value(LAST_FOLDER_KEY, "", type=str)
        folder, source = default_output_folder(last, QgsProject.instance().homePath())
        self.edit_folder.setText(folder)
        self.label_folder.setText(tr(FOLDER_HINT[source]))

    def layer(self):
        lid = self.combo.currentData()
        return QgsProject.instance().mapLayer(lid) if lid else None

    def update_info(self):
        layer = self.layer()
        project_crs = QgsProject.instance().crs()
        if layer is None:
            self.label_crs.setText(tr("p1_no_polygons"))
            self.check_selected.setEnabled(False)
            return
        n_sel = layer.selectedFeatureCount()
        self.check_selected.setEnabled(n_sel > 0)
        self.check_selected.setChecked(n_sel > 0)
        self.check_selected.setText(tr("p1_selected_only") + f" ({n_sel})")
        ok_l = tr("ok") if crs_in_meters(layer.crs()) else tr("not_meters")
        ok_p = tr("ok") if crs_in_meters(project_crs) else tr("not_meters")
        self.label_crs.setText(tr("p1_crs_info", layer_crs=crs_code(layer.crs()), ok_l=ok_l,
                                  project_crs=crs_code(project_crs), ok_p=ok_p))

    def choose_folder(self):
        start = self.edit_folder.text().strip()
        while start and not os.path.isdir(start):     # e.g. AgriPrecisa not created yet
            start = os.path.dirname(start) if os.path.dirname(start) != start else ""
        folder = QFileDialog.getExistingDirectory(self, tr("p1_folder_dialog"), start)
        if folder:
            self.edit_folder.setText(folder)
            self.label_folder.setText("")

    def validatePage(self):
        layer = self.layer()
        if layer is None:
            QMessageBox.warning(self, tr("p1_boundary"), tr("p1_err_choose"))
            return False
        selected = self.check_selected.isChecked() and layer.selectedFeatureCount() > 0
        feats = list(layer.getSelectedFeatures() if selected else layer.getFeatures())
        extent = features_extent(feats)
        geom = boundary_geometry(feats)
        if extent is None or geom is None:
            QMessageBox.warning(self, tr("p1_boundary"), tr("p1_err_empty"))
            return False
        if not crs_in_meters(layer.crs()):
            QMessageBox.warning(self, tr("project_layer_title"),
                                tr("p1_err_crs", name=layer.name(), crs=crs_code(layer.crs())))
            return False
        if not crs_in_meters(QgsProject.instance().crs()):
            answer = QMessageBox.question(self, tr("project_title"),
                                          tr("p1_ask_project_crs", crs=crs_code(QgsProject.instance().crs())))
            if answer != QMessageBox.StandardButton.Yes:
                return False
        folder = self.edit_folder.text().strip()
        if not prepare_output_folder(folder):
            QMessageBox.warning(self, tr("p1_folder"), tr("p1_err_folder"))
            return False
        QgsSettings().setValue(LAST_FOLDER_KEY, folder)

        w = self.wizard()
        w.boundary = layer
        w.selected_only = selected
        w.boundary_extent = extent
        w.boundary_geom = geom
        w.area_ha = geom.area() / 10000.0
        w.tolerance = self.spin_tol.value()
        w.folder = folder
        return True


# ---------------------------------------------------------------------------
# Page 2: point layers and fields (expandable tree)
# ---------------------------------------------------------------------------
COL_LAYER, COL_CRS, COL_POINTS = 0, 1, 2


def crs_status(crs):
    """Return (ok, tooltip key) describing whether the CRS can be used."""
    if not crs.isValid():
        return False, "p2_tip_invalid"
    if crs.isGeographic():
        return False, "p2_tip_geographic"
    if not crs_in_meters(crs):
        return False, "p2_tip_not_meters"
    return True, "p2_tip_ok"


def crs_code(crs):
    if not crs.isValid():
        return tr("p2_no_crs")
    return crs.authid() or crs.description()


def layer_label(layer):
    """'Layer name [EPSG:xxxx]', as QGIS shows it in its layer selectors."""
    return f"{layer.name()} [{crs_code(layer.crs())}]"


def set_crs_cell(item, crs):
    """Warning icon to the right of the layer name, with tooltip, when not in metres."""
    ok, tip_key = crs_status(crs)
    tip = tr(tip_key, crs=crs_code(crs))
    item.setToolTip(COL_LAYER, tip)
    if not ok:
        item.setIcon(COL_CRS, QgsApplication.getThemeIcon("/mIconWarning.svg"))
        item.setToolTip(COL_CRS, tip)
    item.setData(COL_CRS, Qt.ItemDataRole.UserRole, ok)


class PointsPage(QWizardPage):
    help_key = "help_page2"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("p2_title"))
        self.setSubTitle(tr("p2_subtitle"))

        self.tree = QTreeWidget()
        # column 1 is a narrow, untitled column that only holds the warning icon,
        # so the icon sits to the right of "Layer name [EPSG:xxxx]"
        self.tree.setHeaderLabels([tr("p2_col_layer"), "", tr("p2_col_points")])
        self.tree.setColumnWidth(COL_LAYER, 330)
        self.tree.setColumnWidth(COL_CRS, 28)

        buttons = QHBoxLayout()
        for key, func in (("expand_all", lambda: self.tree.expandAll()),
                          ("collapse_all", lambda: self.tree.collapseAll()),
                          ("check_all", lambda: self.set_all(True)),
                          ("uncheck_all", lambda: self.set_all(False))):
            b = QPushButton(tr(key))
            b.clicked.connect(func)
            buttons.addWidget(b)

        self.label = QLabel()
        self.label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.tree)
        layout.addLayout(buttons)
        layout.addWidget(self.label)

    def initializePage(self):
        w = self.wizard()
        self.setSubTitle(tr("p2_subtitle_area", area=fmt(w.area_ha, 2)))
        self.tree.clear()
        w.layer_stats = {}
        rect = buffered(w.boundary_extent, w.tolerance)
        tctx = QgsProject.instance().transformContext()
        found = 0
        for layer in QgsProject.instance().mapLayers().values():
            if not (isinstance(layer, QgsVectorLayer) and layer.geometryType() == GEOM_POINT):
                continue
            fields = [f.name() for f in layer.fields() if f.isNumeric()]
            if not fields:
                continue
            try:
                stats = sample_stats(layer, fields, w.boundary_geom, w.boundary.crs(), rect, tctx)
            except Exception:
                continue
            if stats["used"] == 0:
                continue
            w.layer_stats[layer.id()] = stats
            found += 1
            parent = QTreeWidgetItem([layer_label(layer), "", ""])
            self.set_count_cell(parent, stats["inside"], stats["used"])
            set_crs_cell(parent, layer.crs())
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                            | Qt.ItemFlag.ItemIsAutoTristate)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            for name in fields:
                child = QTreeWidgetItem([name, "", ""])
                child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, (layer.id(), name))
                parent.addChild(child)
            self.tree.addTopLevelItem(parent)
        self.tree.resizeColumnToContents(COL_LAYER)
        self.label.setText(tr("p2_none") if found == 0 else tr("p2_found", n=found))

    def set_count_cell(self, item, inside, used):
        """'4.969 (39,8 amostras/ha)', left-aligned, shown on layer rows only;
        the tooltip tells how many samples interpolation will use."""
        w = self.wizard()
        density = fmt(sample_density(inside, w.area_ha), 1)
        item.setText(COL_POINTS, tr("p2_count", n=fmt(inside), density=density))
        item.setToolTip(COL_POINTS, tr("p2_tip_count", inside=fmt(inside), density=density,
                                       used=fmt(used), tol=fmt(w.tolerance)))
        item.setTextAlignment(COL_POINTS, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def set_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, state)

    def selection(self):
        out = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    lid, field = child.data(0, Qt.ItemDataRole.UserRole)
                    out.append((QgsProject.instance().mapLayer(lid), field))
        return out

    def validatePage(self):
        sel = self.selection()
        if not sel:
            QMessageBox.warning(self, tr("p2_title"), tr("p2_err_none"))
            return False
        bad = sorted({f"{l.name()} ({crs_code(l.crs())})" for l, _ in sel if not crs_in_meters(l.crs())})
        if bad:
            QMessageBox.warning(self, tr("project_layer_title"), tr("p2_err_crs", layers="\n".join(bad)))
            return False
        self.wizard().items = sel
        return True


# ---------------------------------------------------------------------------
# Page 4: summary
# ---------------------------------------------------------------------------
class SummaryPage(QWizardPage):
    help_key = "help_page4"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("p4_title"))
        self.setSubTitle(tr("p4_subtitle"))
        self.text = QTextBrowser()
        layout = QVBoxLayout(self)
        layout.addWidget(self.text)
        self.setFinalPage(True)

    def initializePage(self):
        w = self.wizard()
        origins = getattr(w, "param_origins", ["default"] * len(w.items))
        items = "".join(
            tr("p4_item", layer=l.name(), field=f, p=fmt(p, 1),
               r=tr("no_limit") if r == 0 else fmt(r) + " m", origin=tr(ORIGIN_TEXT[o]))
            for (l, f), (p, r), o in zip(w.items, w.params, origins))
        sel = f" ({tr('selected_features')})" if w.selected_only else ""
        self.text.setHtml(tr(
            "p4_summary", boundary=w.boundary.name() + sel, crs=crs_code(w.boundary.crs()),
            area=fmt(w.area_ha, 2),
            tol=f"{w.tolerance:g}", folder=w.folder, n=len(w.items), items=items,
            pixel=f"{w.pixel:g}", classes=N_CLASSES, ramp=COLOR_RAMP))


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------
class IdwWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("wizard_title"))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, True)
        self.setButtonText(QWizard.WizardButton.HelpButton, tr("help"))
        self.setButtonText(QWizard.WizardButton.NextButton, tr("next"))
        self.setButtonText(QWizard.WizardButton.BackButton, tr("back"))
        self.setButtonText(QWizard.WizardButton.FinishButton, tr("run"))
        self.setButtonText(QWizard.WizardButton.CancelButton, tr("cancel"))
        self.setMinimumSize(880, 680)
        self.resize(1000, 880)

        self.boundary = None
        self.selected_only = False
        self.boundary_extent = None
        self.boundary_geom = None
        self.area_ha = 0.0
        self.layer_stats = {}
        self.tolerance = 50.0
        self.folder = ""
        self.items = []
        self.params = []          # (power, radius) per item, set in step 3
        self.param_origins = []
        self.pixel = 5.0

        for page in (BoundaryPage(), PointsPage(), ParametersPage(), SummaryPage()):
            self.addPage(page)
        self.helpRequested.connect(self.show_help)

    def show_help(self):
        box = QMessageBox(self)
        box.setWindowTitle(tr("help"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(tr(getattr(self.currentPage(), "help_key", "help_page1")))
        box.exec()


class _DialogFeedback(QgsProcessingFeedback):
    """Processing feedback that drives a QProgressDialog."""

    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.progressChanged.connect(self._on_progress)

    def _on_progress(self, value):
        self.dialog.setValue(int(value))
        QCoreApplication.processEvents()
        if self.dialog.wasCanceled():
            self.cancel()

    def pushInfo(self, info):
        super().pushInfo(info)
        self.dialog.setLabelText(info)
        QCoreApplication.processEvents()


def load_results(result, wizard):
    """One styled copy of the output per field, inside the 'Interpolated' group."""
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    group_name = tr("group_name")
    group = root.findGroup(group_name) or root.insertGroup(0, group_name)
    first = None
    for i, info in enumerate(result["layers"]):
        r = tr("no_limit") if info["radius"] == 0 else f"R={info['radius']:.0f} m"
        name = f"{info['label']} | IDW P={info['power']:g} {r} {wizard.pixel:g} m"
        layer = QgsVectorLayer(result["output"], name, "ogr")
        if not layer.isValid():
            result["warnings"].append(tr("warn_load", label=info["label"]))
            continue
        style_graduated(layer, info["mean_field"])
        project.addMapLayer(layer, False)
        node = group.addLayer(layer)
        node.setItemVisibilityChecked(i == 0)
        first = first or layer
    group.setExpanded(True)
    return first


def run_wizard(iface):
    wizard = IdwWizard(iface.mainWindow())
    if wizard.exec() != QDialog.DialogCode.Accepted:
        return

    stamp = datetime.datetime.now().strftime("_%Y%m%d_%H%M%S")
    boundary_input = wizard.boundary
    if wizard.selected_only:
        boundary_input = QgsProcessingFeatureSourceDefinition(wizard.boundary.id(), True)
    job = IdwJob(boundary_input, wizard.boundary_extent, wizard.boundary.crs(), wizard.items,
                 wizard.tolerance, 2.0, 0.0, wizard.pixel,
                 wizard.folder, os.path.join(wizard.folder, f"Grid_IDW{stamp}.gpkg"), stamp,
                 params=wizard.params)

    progress = QProgressDialog(tr("starting"), tr("cancel"), 0, 100, iface.mainWindow())
    progress.setWindowTitle(tr("wizard_title"))
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    feedback = _DialogFeedback(progress)
    context = QgsProcessingContext()
    context.setProject(QgsProject.instance())

    try:
        result = run_idw_job(job, context, feedback)
    except QgsProcessingException as e:
        progress.close()
        if feedback.isCanceled():
            return
        QMessageBox.warning(iface.mainWindow(), tr("wizard_title"), str(e))
        return
    except Exception:
        progress.close()
        QMessageBox.critical(iface.mainWindow(), tr("error_title"), traceback.format_exc())
        return

    first = load_results(result, wizard)
    progress.close()
    if first is not None:
        canvas = iface.mapCanvas()
        canvas.setExtent(rect_to_crs(first.extent(), first.crs(), QgsProject.instance().crs(),
                                     QgsProject.instance().transformContext()))
        canvas.refresh()

    summary = "\n".join(tr("done_line", label=i["label"], n=i["n"]) for i in result["layers"])
    msg = tr("done_msg", summary=summary, folder=wizard.folder,
             output=os.path.basename(result["output"]))
    if result["warnings"]:
        msg += "\n\n" + tr("warnings") + "\n" + "\n".join(result["warnings"])
    QMessageBox.information(iface.mainWindow(), tr("wizard_title"), msg)
