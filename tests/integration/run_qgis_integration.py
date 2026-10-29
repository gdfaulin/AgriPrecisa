"""
Integration test that needs a QGIS installation (not run by plain pytest).

Usage (Linux):  QT_QPA_PLATFORM=offscreen python3 tests/integration/run_qgis_integration.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
for p in ("/usr/share/qgis/python/plugins", "/usr/share/qgis/python"):
    if os.path.isdir(p):
        sys.path.append(p)

from qgis.core import (QgsApplication, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY,
                       QgsProject, QgsProcessingContext, QgsProcessingFeedback,
                       QgsGraduatedSymbolRenderer)

app = QgsApplication([], True)
app.initQgis()
import processing
from processing.core.Processing import Processing
Processing.initialize()

from agriprecisa.processing_provider.provider import AgriPrecisaProvider
from agriprecisa.core.pipeline import IdwJob, run_idw_job, features_extent
from agriprecisa import i18n

provider = AgriPrecisaProvider()
QgsApplication.processingRegistry().addProvider(provider)

X0, Y0 = 600000.0, 7550000.0
boundary = QgsVectorLayer("Polygon?crs=EPSG:31982", "talhao", "memory")
f = QgsFeature()
f.setGeometry(QgsGeometry.fromWkt(
    f"POLYGON(({X0} {Y0},{X0+200} {Y0},{X0+200} {Y0+100},{X0+100} {Y0+150},{X0} {Y0+100},{X0} {Y0}))"))
boundary.dataProvider().addFeatures([f])

points = QgsVectorLayer("Point?crs=EPSG:31982&field=argila:double&field=pH:double&field=nome:string",
                        "amostras", "memory")
feats = []
for i in range(5):
    for j in range(4):
        p = QgsFeature(points.fields())
        x, y = X0 - 10 + i * 55, Y0 - 10 + j * 50   # a few samples fall outside the boundary
        p.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        p.setAttributes([200 + i * 50.0, 5.0 + j * 0.3 if (i, j) != (2, 2) else None, "a"])
        feats.append(p)
points.dataProvider().addFeatures(feats)
QgsProject.instance().addMapLayers([boundary, points])

tmp = tempfile.mkdtemp()
errors = []

# 1) Processing algorithm, as used from the toolbox / modeler
out = os.path.join(tmp, "grid.gpkg")
res = processing.run("agriprecisa:idw_vector_grid", {
    "BOUNDARY": boundary, "POINTS": points, "FIELDS": ["argila", "pH"],
    "TOLERANCE": 50, "POWER": 2, "RADIUS": 0, "PIXEL": 5,
    "RASTER_FOLDER": os.path.join(tmp, "rasters"), "OUTPUT": out})
grid = QgsVectorLayer(res["OUTPUT"], "g", "ogr")
names = [fl.name() for fl in grid.fields()]
print("Processing output fields:", names, "features:", grid.featureCount())
print("raster folder:", sorted(os.listdir(os.path.join(tmp, "rasters"))))
if not {"argila_mean", "pH_mean"} <= set(names):
    errors.append("missing mean fields")
if grid.featureCount() == 0:
    errors.append("empty grid")
vals = [ft["argila_mean"] for ft in grid.getFeatures()]
lo, hi = min(v for v in vals if v is not None), max(v for v in vals if v is not None)
print(f"argila_mean range: {lo:.1f} .. {hi:.1f}")
if not (200 <= lo and hi <= 400):
    errors.append("argila_mean outside sample range")
area = sum(ft.geometry().area() for ft in grid.getFeatures())
print(f"grid area {area:.1f} m2 (boundary 25000 m2)")
if abs(area - 25000) > 1:
    errors.append("grid area differs from boundary area")
if len([n for n in os.listdir(os.path.join(tmp, "rasters")) if n.endswith(".tif")]) != 2:
    errors.append("expected 2 rasters")

# 2) Shared pipeline as called by the wizard, with selected features only
from qgis.core import QgsProcessingFeatureSourceDefinition
boundary.selectAll()
ctx = QgsProcessingContext(); ctx.setProject(QgsProject.instance())
job = IdwJob(QgsProcessingFeatureSourceDefinition(boundary.id(), True),
             features_extent(boundary.getSelectedFeatures()), boundary.crs(),
             [(points, "argila"), (points, "pH")], 50, 2, 100, 10, tmp,
             os.path.join(tmp, "wizard.gpkg"), "_t")
r = run_idw_job(job, ctx, QgsProcessingFeedback())
print("Wizard pipeline layers:", [l["mean_field"] for l in r["layers"]], "n:", [l["n"] for l in r["layers"]])
if [l["n"] for l in r["layers"]] != [20, 19]:
    errors.append("unexpected sample counts (NULL pH must be skipped)")

# 3) GUI pieces: wizard construction in 3 languages, styling and results loading
from unittest import mock
from qgis.PyQt.QtWidgets import QMainWindow, QToolBar
main = QMainWindow()
iface = mock.MagicMock()
iface.mainWindow.return_value = main
iface.addToolBar.side_effect = lambda name: QToolBar(name, main)
from agriprecisa.gui import idw_wizard
for lang in ("pt", "en", "es"):
    i18n.set_language(lang)
    w = idw_wizard.IdwWizard()
    for pid in w.pageIds():
        w.page(pid)  # pages built without errors
    print(lang, "wizard title:", w.windowTitle())

class W: power = 2.0; pixel = 10.0
first = idw_wizard.load_results(r, W)
group = QgsProject.instance().layerTreeRoot().findGroup(i18n.tr("group_name"))
print("group children:", [c.name() for c in group.children()])
if len(group.children()) != 2:
    errors.append("expected 2 layers in group")
rend = first.renderer()
if not isinstance(rend, QgsGraduatedSymbolRenderer) or len(rend.ranges()) != 5:
    errors.append("graduated renderer with 5 classes not applied")
print("classes:", [f"{x.lowerValue():.1f}-{x.upperValue():.1f}" for x in rend.ranges()])


# 3b) Step 2: "name [EPSG:xxxx]" and a warning icon (with tooltip) to the right for non-metric layers
geo = QgsVectorLayer("Point?crs=EPSG:4326&field=SHALLOW:double&field=DEEP:double", "CE Limpo", "memory")
from qgis.core import QgsCoordinateTransform
ct = QgsCoordinateTransform(points.crs(), geo.crs(), QgsProject.instance())
gfeats = []
for ft in points.getFeatures():
    g = QgsFeature(geo.fields())
    gg = QgsGeometry(ft.geometry()); gg.transform(ct)
    g.setGeometry(gg); g.setAttributes([ft["argila"], ft["argila"]])
    gfeats.append(g)
geo.dataProvider().addFeatures(gfeats)
QgsProject.instance().addMapLayer(geo)
i18n.set_language("pt")
# headless run: answer message boxes automatically instead of blocking
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import Qt
popups = []
QMessageBox.question = staticmethod(lambda *a, **k: (popups.append(a[2]), QMessageBox.StandardButton.Yes)[1])
QMessageBox.warning = staticmethod(lambda *a, **k: (popups.append(a[2]), QMessageBox.StandardButton.Ok)[1])
wz = idw_wizard.IdwWizard()
wz.show()
p1 = wz.currentPage()
p1.combo.setCurrentIndex(p1.combo.findData(boundary.id()))
p1.edit_folder.setText(tmp)
wz.next()
if popups:
    print("popups:", popups)
# Regression: with no project CRS the message read "O projeto está em , que não ..."
if any("está em ," in m for m in popups):
    errors.append("empty CRS name in project CRS message")
page = wz.currentPage()
page.tree.expandAll()
rows = {}
for i in range(page.tree.topLevelItemCount()):
    it = page.tree.topLevelItem(i)
    rows[it.text(0)] = (not it.icon(1).isNull(), it.toolTip(1), it.text(2))
print("Step 2 rows:", {k: ("WARNING ICON" if v[0] else "no icon", v[2]) for k, v in rows.items()})
print("Step 2 subtitle:", page.subTitle())
if "2,50 ha" not in page.subTitle():
    errors.append("field area (2,50 ha) missing from step 2 header")
amostras = page.tree.findItems("amostras [EPSG:31982]", Qt.MatchFlag.MatchExactly, 0)[0]
kids = {amostras.child(k).text(0): amostras.child(k).text(2) for k in range(amostras.childCount())}
print("Counts:", repr(amostras.text(2)), kids)
print("Count tooltip:", amostras.toolTip(2))
if amostras.text(2) != "7 (2,8 amostras/ha)":
    errors.append("layer row should show '7 (2,8 amostras/ha)'")
if any(kids.values()):
    errors.append("attribute rows must not show counts (only layer rows)")
if not (amostras.textAlignment(2) & int(Qt.AlignmentFlag.AlignLeft)):
    errors.append("counts must be left-aligned")
if "serão usadas 20" not in amostras.toolTip(2):
    errors.append("tooltip should report the 20 samples used with tolerance")
if not rows.get("CE Limpo [EPSG:4326]", (False,))[0]:
    errors.append("geographic layer without '[EPSG:4326]' label or warning icon")
elif "metros" not in rows["CE Limpo [EPSG:4326]"][1]:
    errors.append("tooltip text missing")
if rows.get("amostras [EPSG:31982]", (True,))[0]:
    errors.append("metric layer should be labelled [EPSG:31982] without icon")
print("Tooltip:", rows.get("CE Limpo [EPSG:4326]", ("", ""))[1])
app.processEvents()
shot = os.environ.get("AGRIPRECISA_SHOT")
if shot:
    wz.grab().save(shot)

# 3c) Step 3 (student mode): sliders, texts, spacing, curve and live preview
from qgis.core import QgsSettings
QgsSettings().remove("AgriPrecisa/idw_student_mode")   # first run -> student mode
for k in range(amostras.childCount()):
    amostras.child(k).setCheckState(0, Qt.CheckState.Checked)
wz.next()
p3 = wz.currentPage()
print("Step 3 page:", p3.title())
if not p3.radio_student.isChecked():
    errors.append("step 3 should open in student mode by default")
print("Spacing:", round(p3.spacing, 1), "m; radius:", p3.radius(), "m; P:", p3.power())
# coverage distance of a ~55 x 50 m grid: between the typical distance and the half diagonal
if not (p3.typical < p3.spacing < 45):
    errors.append(f"unexpected coverage distance {p3.spacing:.1f} m (typical {p3.typical:.1f} m)")
if not p3.check_points.isChecked():
    errors.append("few samples: preview should start showing the samples")
p3.check_points.setChecked(False)
if p3.preview.show_points:
    errors.append("'Mostrar amostras' did not hide the samples")
p3.check_points.setChecked(True)
if abs(p3.radius() - round(2 * p3.spacing, 1)) > 0.05:
    errors.append("default radius should be 2x the spacing")
p3.slider_p.setValue(30)
p3.slider_r.setValue(12)
app.processEvents()
print("P text:", p3.label_p_text.text()[:60], "...")
print("R value:", p3.label_r_value.text())
print("R text:", p3.label_r_text.text()[:50], "...")
if "P alto" not in p3.label_p_text.text() or "Saiba mais" not in p3.label_p_text.text():
    errors.append("high-P text or 'Saiba mais' link missing")
if "Raio curto" not in p3.label_r_text.text():
    errors.append("short-radius text missing")
p3.slider_p.setValue(10)
if "P baixo" not in p3.label_p_text.text():
    errors.append("low-P text missing")
p3.slider_p.setValue(20)
p3.slider_r.setValue(20)
p3.refresh_preview()
print("Preview range:", p3.preview.value_range)
# Regression: the inside/outside mask was always empty (temporary point geometry freed
# before GEOS used it), so the preview showed nothing.
inside_cells = int(p3.preview.mask.sum())
print("Preview cells inside the field:", inside_cells, "of", p3.preview.mask.size)
cell_area = p3.preview.grid[4] ** 2
if not (0.9 * 25000 < inside_cells * cell_area < 1.1 * 25000):
    errors.append("preview mask should cover about the field area (25000 m2)")
if p3.preview.image is None or p3.preview.value_range is None:
    errors.append("live preview not rendered")
if p3.curve.power != 2.0:
    errors.append("weight curve not following P")
# preview attribute selector
p3.combo_attr.setCurrentIndex(1)
p3.refresh_preview()
print("Preview attribute:", p3.combo_attr.currentText(), "| samples:", p3.preview.points[2].size)
if p3.preview.points[2].size != 19:
    errors.append("preview for pH should use the 19 non-empty samples")
p3.combo_attr.setCurrentIndex(0)
p3.refresh_preview()
app.processEvents()
cmp_dir = os.environ.get("AGRIPRECISA_SHOT_CMP")
if cmp_dir:
    for pv in (10, 30):
        p3.slider_p.setValue(pv)
        p3.refresh_preview()
        app.processEvents()
        p3.stack.currentWidget().grab().save(os.path.join(cmp_dir, f"p{pv}.png"))
    p3.slider_p.setValue(20)
    p3.refresh_preview()
shot3 = os.environ.get("AGRIPRECISA_SHOT3")
if shot3:
    wz.grab().save(shot3)
# switch to advanced: values carried over; mode remembered
p3.radio_advanced.setChecked(True)
print("Advanced:", p3.spin_p.value(), p3.spin_r.value())
if p3.spin_p.value() != 2.0 or abs(p3.spin_r.value() - round(2 * p3.spacing, 1)) > 0.1:
    errors.append("values not carried to advanced mode")
if QgsSettings().value("AgriPrecisa/idw_student_mode", True, type=bool):
    errors.append("mode choice not remembered")
p3.spin_p.setValue(5.0)
p3.radio_student.setChecked(True)
if p3.slider_p.value() != 30:
    errors.append("P above 3 should be clamped to 3 when returning to student mode")
p3.validatePage()
print("Wizard values:", wz.power, wz.radius, wz.pixel)
wz.hide()

# 3d) Sensor passes (like EC): coverage distance and cross-validation
import math as _m
import numpy as _np
rng = _np.random.default_rng(7)
ce = QgsVectorLayer("Point?crs=EPSG:31982&field=CE:double", "ce_sensor", "memory")
cfeats = []
for yy in _np.arange(5, 150, 15.0):                  # passes every 15 m
    for xx in _np.arange(-5, 206, 2.0):              # points every 2 m along the pass
        f2 = QgsFeature(ce.fields())
        f2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X0 + xx, Y0 + yy)))
        val = 2 + 0.01 * xx + 0.5 * _m.sin(yy / 30.0) + rng.normal(0, 0.05)
        f2.setAttributes([float(val)])
        cfeats.append(f2)
ce.dataProvider().addFeatures(cfeats)
QgsProject.instance().addMapLayer(ce)
from agriprecisa.gui import params_page as _pp
dialogs = []
_pp.CrossValidationDialog.exec = lambda self: (dialogs.append(self), 1)[1]
wz2 = idw_wizard.IdwWizard()
wz2.show()
q1 = wz2.currentPage()
q1.combo.setCurrentIndex(q1.combo.findData(boundary.id()))
q1.edit_folder.setText(tmp)
wz2.next()
q2 = wz2.currentPage()
item_ce = q2.tree.findItems("ce_sensor [EPSG:31982]", Qt.MatchFlag.MatchExactly, 0)[0]
item_ce.child(0).setCheckState(0, Qt.CheckState.Checked)
wz2.next()
q3 = wz2.currentPage()
n_ce = q3.preview.points[2].size
density_spacing = (10000 / (q2.wizard().layer_stats[ce.id()]["inside"] / wz2.area_ha)) ** 0.5
print(f"Sensor: {n_ce} points; density-based spacing {density_spacing:.1f} m; "
      f"coverage {q3.spacing:.1f} m; typical {q3.typical:.1f} m")
# passes 15 m apart -> the farthest pixels are ~7.5 m from a pass; density alone says ~5.5 m
if not (q3.spacing > density_spacing and 6.5 < q3.spacing < 7.6):
    errors.append("coverage distance should see the 15 m gap between passes (~7 m), not the density spacing")
if q3.check_points.isChecked():
    errors.append("many samples: preview should start with samples hidden")
q3.radio_student.setChecked(True)
q3.run_cross_validation()
if not dialogs:
    errors.append("cross-validation dialog not shown")
else:
    dlg = dialogs[-1]
    print("CV summary:", dlg.result_summary, "| table", dlg.table.rowCount(), "x", dlg.table.columnCount())
    print("CV label:", q3.label_cv.text()[:80])
    best_p = dlg.result_summary["power"]
    if abs(q3.slider_p.value() / 10.0 - best_p) > 1e-6:
        errors.append("'Aplicar' did not move the P slider to the suggested value")
    if abs(q3.slider_r.value() / 10.0 - dlg.result_summary["multiple"]) > 1e-6:
        errors.append("'Aplicar' did not move the radius slider")
    if "Sugestão" not in q3.label_cv.text() or "0,0391" not in q3.label_cv.text():
        errors.append("suggestion text missing")
    shot_cv = os.environ.get("AGRIPRECISA_SHOT_CV")
    if shot_cv:
        dlg.show(); app.processEvents()
        if dlg.table.height() < dlg.table.minimumHeight():
            errors.append("cross-validation table is cut")
        dlg.grab().save(shot_cv); dlg.hide()
q3.refresh_preview(); app.processEvents()
shot4 = os.environ.get("AGRIPRECISA_SHOT4")
if shot4:
    wz2.grab().save(shot4)
wz2.hide()
QgsProject.instance().removeMapLayer(ce.id())
QgsProject.instance().removeMapLayer(geo.id())

# 4) Plugin load/unload through classFactory
import agriprecisa
QgsApplication.processingRegistry().removeProvider(provider)
plg = agriprecisa.classFactory(iface)
plg.initGui()
reg = QgsApplication.processingRegistry().providerById("agriprecisa") is not None
print("provider registered by plugin:", reg)
if not reg:
    errors.append("plugin did not register its provider")
plg.unload()
if QgsApplication.processingRegistry().providerById("agriprecisa") is not None:
    errors.append("provider still registered after unload")

# Regression: a provider with the same id already registered made unload() crash
# ("wrapped C/C++ object ... has been deleted").
blocker = AgriPrecisaProvider()
QgsApplication.processingRegistry().addProvider(blocker)
plg = agriprecisa.classFactory(iface)
plg.initGui()
try:
    plg.unload()
    print("regression duplicate provider: OK")
except RuntimeError as e:
    errors.append(f"unload crashed with duplicate provider: {e}")
QgsApplication.processingRegistry().removeProvider(blocker)
print("\nRESULT:", "FAILED " + "; ".join(errors) if errors else "ALL INTEGRATION CHECKS PASSED")
sys.stdout.flush()
# os._exit skips the QGIS teardown, which can segfault in headless test runs
os._exit(1 if errors else 0)
