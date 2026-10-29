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
    QgsProject, QgsVectorLayer, QgsProcessingContext, QgsProcessingFeedback,
    QgsProcessingException, QgsProcessingFeatureSourceDefinition,
)

from ..core.compat import GEOM_POINT, GEOM_POLYGON
from ..core.pipeline import (
    IdwJob, run_idw_job, crs_in_meters, buffered, count_points, features_extent,
    style_graduated, rect_to_crs, N_CLASSES, COLOR_RAMP,
)
from ..core.idw_math import snap_extent
from ..i18n import tr


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

        self.label_crs = QLabel()
        self.label_crs.setWordWrap(True)
        self.combo.currentIndexChanged.connect(self.update_info)

        form = QFormLayout()
        form.addRow(tr("p1_boundary"), self.combo)
        form.addRow("", self.check_selected)
        form.addRow(tr("p1_tolerance"), self.spin_tol)
        form.addRow(tr("p1_folder"), row)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.label_crs)
        layout.addStretch()

    def initializePage(self):
        self.combo.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer) and layer.geometryType() == GEOM_POLYGON:
                self.combo.addItem(layer.name(), layer.id())
        self.update_info()

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
        self.label_crs.setText(tr("p1_crs_info", layer_crs=layer.crs().authid(), ok_l=ok_l,
                                  project_crs=project_crs.authid(), ok_p=ok_p))

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("p1_folder_dialog"))
        if folder:
            self.edit_folder.setText(folder)

    def validatePage(self):
        layer = self.layer()
        if layer is None:
            QMessageBox.warning(self, tr("p1_boundary"), tr("p1_err_choose"))
            return False
        selected = self.check_selected.isChecked() and layer.selectedFeatureCount() > 0
        feats = layer.getSelectedFeatures() if selected else layer.getFeatures()
        extent = features_extent(feats)
        if extent is None:
            QMessageBox.warning(self, tr("p1_boundary"), tr("p1_err_empty"))
            return False
        if not crs_in_meters(layer.crs()):
            QMessageBox.warning(self, tr("project_layer_title"),
                                tr("p1_err_crs", name=layer.name(), crs=layer.crs().authid()))
            return False
        if not crs_in_meters(QgsProject.instance().crs()):
            answer = QMessageBox.question(self, tr("project_title"),
                                          tr("p1_ask_project_crs", crs=QgsProject.instance().crs().authid()))
            if answer != QMessageBox.StandardButton.Yes:
                return False
        folder = self.edit_folder.text().strip()
        if not folder or not os.path.isdir(folder) or not os.access(folder, os.W_OK):
            QMessageBox.warning(self, tr("p1_folder"), tr("p1_err_folder"))
            return False

        w = self.wizard()
        w.boundary = layer
        w.selected_only = selected
        w.boundary_extent = extent
        w.tolerance = self.spin_tol.value()
        w.folder = folder
        return True


# ---------------------------------------------------------------------------
# Page 2: point layers and fields (expandable tree)
# ---------------------------------------------------------------------------
class PointsPage(QWizardPage):
    help_key = "help_page2"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("p2_title"))
        self.setSubTitle(tr("p2_subtitle"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("p2_col_layer"), tr("p2_col_points")])
        self.tree.setColumnWidth(0, 330)

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
        self.tree.clear()
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
                n = count_points(layer, rect, w.boundary.crs(), tctx)
            except Exception:
                n = 0
            if n == 0:
                continue
            found += 1
            parent = QTreeWidgetItem([layer.name(), str(n)])
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                            | Qt.ItemFlag.ItemIsAutoTristate)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            for name in fields:
                child = QTreeWidgetItem([name, ""])
                child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, (layer.id(), name))
                parent.addChild(child)
            self.tree.addTopLevelItem(parent)
        self.label.setText(tr("p2_none") if found == 0 else tr("p2_found", n=found))

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
        bad = sorted({f"{l.name()} ({l.crs().authid()})" for l, _ in sel if not crs_in_meters(l.crs())})
        if bad:
            QMessageBox.warning(self, tr("project_layer_title"), tr("p2_err_crs", layers="\n".join(bad)))
            return False
        self.wizard().items = sel
        return True


# ---------------------------------------------------------------------------
# Page 3: IDW parameters
# ---------------------------------------------------------------------------
class ParametersPage(QWizardPage):
    help_key = "help_page3"

    def __init__(self):
        super().__init__()
        self.setTitle(tr("p3_title"))
        self.setSubTitle(tr("p3_subtitle"))

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

        self.spin_px = QDoubleSpinBox()
        self.spin_px.setRange(0.1, 1000)
        self.spin_px.setDecimals(2)
        self.spin_px.setValue(5.0)
        self.spin_px.setSuffix(" m")
        self.spin_px.valueChanged.connect(self.estimate)

        self.label = QLabel()
        self.label.setWordWrap(True)

        form = QFormLayout()
        form.addRow(tr("p3_power"), self.spin_p)
        form.addRow(tr("p3_radius"), self.spin_r)
        form.addRow(tr("p3_pixel"), self.spin_px)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.label)
        layout.addStretch()

    def initializePage(self):
        self.estimate()

    def estimate(self):
        w = self.wizard()
        if w is None or w.boundary_extent is None:
            return
        e = w.boundary_extent
        *_, ncol, nrow = snap_extent(e.xMinimum(), e.yMinimum(), e.xMaximum(), e.yMaximum(),
                                     self.spin_px.value())
        total = ncol * nrow
        text = tr("p3_estimate", ncol=ncol, nrow=nrow, total=f"{total:,}".replace(",", "."))
        if total > 5_000_000:
            text += "<br>" + tr("p3_big")
        self.label.setText(text)

    def validatePage(self):
        w = self.wizard()
        w.power = self.spin_p.value()
        w.radius = self.spin_r.value()
        w.pixel = self.spin_px.value()
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
        items = "".join(f"<li>{l.name()}: {f}</li>" for l, f in w.items)
        radius = tr("no_limit") if w.radius == 0 else f"{w.radius:g} m"
        sel = f" ({tr('selected_features')})" if w.selected_only else ""
        self.text.setHtml(tr(
            "p4_summary", boundary=w.boundary.name() + sel, crs=w.boundary.crs().authid(),
            tol=f"{w.tolerance:g}", folder=w.folder, n=len(w.items), items=items,
            power=f"{w.power:g}", radius=radius, pixel=f"{w.pixel:g}",
            classes=N_CLASSES, ramp=COLOR_RAMP))


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
        self.resize(740, 580)

        self.boundary = None
        self.selected_only = False
        self.boundary_extent = None
        self.tolerance = 50.0
        self.folder = ""
        self.items = []
        self.power = 2.0
        self.radius = 100.0
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
        name = f"{info['label']} | IDW P={wizard.power:g} {wizard.pixel:g} m"
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
                 wizard.tolerance, wizard.power, wizard.radius, wizard.pixel,
                 wizard.folder, os.path.join(wizard.folder, f"Grid_IDW{stamp}.gpkg"), stamp)

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
