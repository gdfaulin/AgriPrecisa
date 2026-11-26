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
res = processing.run("agriprecisa:idw_vector_grid", {
    "BOUNDARY": boundary, "POINTS": points, "FIELDS": ["argila", "pH"],
    "TOLERANCE": 50, "POWER": 2, "RADIUS": 0, "PIXEL": 5, "CELL_SIZE": 5,
    "RASTER_FOLDER": os.path.join(tmp, "rasters")})
grid = QgsVectorLayer(res["OUTPUT"], "g", "ogr")
names = [fl.name() for fl in grid.fields()]
print("Processing output:", os.path.basename(res["OUTPUT"]), names, "features:", grid.featureCount())
print("raster folder:", sorted(os.listdir(os.path.join(tmp, "rasters"))))
# 1.8.0: single output, the standard grid with ID 1..n and one column per attribute
std_grid = os.path.join(tmp, "rasters", "talhao_Grade Padrão_5x5.shp")
if os.path.normcase(res["OUTPUT"]) != os.path.normcase(std_grid):
    errors.append("Processing output should be '<boundary>_Grade Padrão_5x5.shp' in the output folder")
if names != ["id", "argila", "pH"]:
    errors.append(f"standard grid should hold only id, argila, pH (got {names})")
_ids = sorted(ft["id"] for ft in grid.getFeatures())
if _ids != list(range(1, len(_ids) + 1)):
    errors.append("grid IDs should be numbered 1, 2, 3... without gaps")
if any("_IDW_" in n for n in os.listdir(os.path.join(tmp, "rasters"))):
    errors.append("the separate _IDW_ result file should no longer be created")
if grid.featureCount() == 0:
    errors.append("empty grid")
vals = [ft["argila"] for ft in grid.getFeatures()]
lo, hi = min(v for v in vals if v is not None), max(v for v in vals if v is not None)
print(f"argila_mean range: {lo:.1f} .. {hi:.1f}")
if not (200 <= lo and hi <= 400):
    errors.append("argila_mean outside sample range")
# Regression: cells clipped by the boundary before the zonal statistics could hold no pixel
# centre and ended with empty (NULL) means along the border
nulls = sum(1 for ft in grid.getFeatures() if ft["argila"] is None or ft["argila"] != ft["argila"])
print("Cells without value:", nulls)
if nulls:
    errors.append(f"{nulls} grid cells without value (NULL mean)")
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
from agriprecisa.core.paths import grid_file_name
grid_path2 = os.path.join(tmp, grid_file_name("talhao", 10))
job = IdwJob(QgsProcessingFeatureSourceDefinition(boundary.id(), True),
             features_extent(boundary.getSelectedFeatures()), boundary.crs(),
             [(points, "argila"), (points, "pH")], 50, 2, 100, 3, tmp,
             grid_path2, "_t", cell_size=10)
r = run_idw_job(job, ctx, QgsProcessingFeedback())
print("Wizard pipeline layers:", [l["mean_field"] for l in r["layers"]], "n:", [l["n"] for l in r["layers"]])
if [l["n"] for l in r["layers"]] != [20, 19]:
    errors.append("unexpected sample counts (NULL pH must be skipped)")


def check_result(path, label):
    lyr = QgsVectorLayer(path, "r", "ogr")
    feats = list(lyr.getFeatures())
    empty = sum(1 for f in feats if f["argila"] is None or f["argila"] != f["argila"]
                or f["pH"] is None or f["pH"] != f["pH"])
    area = sum(f.geometry().area() for f in feats)
    print(f"{label}: {len(feats)} cells, {empty} without value, area {area:.1f} m2,",
          "shp" if path.endswith(".shp") else "other")
    if empty:
        errors.append(f"{label}: {empty} cells without value")
    if abs(area - 25000) > 1:
        errors.append(f"{label}: clipped area should equal the field (25000 m2)")
    return lyr


# cell 10 m, pixel 3 m (not aligned): whole cells, clipped only at the end
check_result(r["output"], "10x10 cells / 3 m pixel")
if r["output"] != grid_path2 or any("_IDW_" in n and n.endswith(".shp") for n in os.listdir(tmp)):
    errors.append("the only result should be '<boundary>_Grade Padrão_10x10.shp'")
saved = QgsVectorLayer(grid_path2, "g", "ogr")
_names = [f.name() for f in saved.fields()]
_ids = sorted(f["id"] for f in saved.getFeatures())
print("Standard grid:", os.path.basename(grid_path2), _names, len(_ids), "cells, ids", _ids[:3], "...", _ids[-1:])
if _names != ["id", "argila", "pH"]:
    errors.append(f"standard grid should hold only id and the attributes, got {_names}")
if _ids != list(range(1, len(_ids) + 1)):
    errors.append("standard grid IDs should be 1, 2, 3... without gaps")
# raster covers the boundary plus the 100 m margin, never clipped
from osgeo import gdal as _gdal
ds = _gdal.Open(r["layers"][0]["raster"])
gt = ds.GetGeoTransform()
r_xmin, r_ymax = gt[0], gt[3]
r_xmax, r_ymin = r_xmin + gt[1] * ds.RasterXSize, r_ymax + gt[5] * ds.RasterYSize
ext = boundary.extent()
print("Raster extent margin (m):", round(ext.xMinimum() - r_xmin, 1), round(r_xmax - ext.xMaximum(), 1),
      round(ext.yMinimum() - r_ymin, 1), round(r_ymax - ext.yMaximum(), 1))
if min(ext.xMinimum() - r_xmin, r_xmax - ext.xMaximum(), ext.yMinimum() - r_ymin, r_ymax - ext.yMaximum()) < 100:
    errors.append("raster should extend at least 100 m beyond the boundary")
ds = None

# 1.8.0: running again adds columns to the standard grid and keeps the previous ones
apath = os.path.join(tmp, grid_file_name("append", 10))
def _run_attrs(attrs, pts=points):
    j = IdwJob(boundary, boundary.extent(), boundary.crs(), [(pts, a) for a in attrs],
               50, 2, 100, 3, tmp, apath, "_a", cell_size=10)
    return run_idw_job(j, ctx, QgsProcessingFeedback())
_run_attrs(["argila"])
first_vals = {f["id"]: f["argila"] for f in QgsVectorLayer(apath, "a", "ogr").getFeatures()}
r_a = _run_attrs(["pH"])
la = QgsVectorLayer(apath, "a", "ogr")
print("Append run:", [f.name() for f in la.fields()], "kept:", r_a["kept"])
if [f.name() for f in la.fields()] != ["id", "pH", "argila"] or r_a["kept"] != ["argila"]:
    errors.append("a second run should add pH and keep argila")
elif any(abs(f["argila"] - first_vals[f["id"]]) > 1e-9 for f in la.getFeatures()):
    errors.append("kept column values should stay attached to the same IDs")
la = None
r_a = _run_attrs(["argila"])
la = QgsVectorLayer(apath, "a", "ogr")
if [f.name() for f in la.fields()] != ["id", "argila", "pH"]:
    errors.append("an attribute computed again should replace its column, not create argila_2")
la = None
# a file that does not match the grid (e.g. an old whole-cell standard grid) is replaced
mism = os.path.join(tmp, grid_file_name("mism", 10))
processing.run("native:creategrid", {"TYPE": 2,
    "EXTENT": f"{X0-50},{X0+50},{Y0-50},{Y0+50} [EPSG:31982]", "HSPACING": 10, "VSPACING": 10,
    "HOVERLAY": 0, "VOVERLAY": 0, "CRS": boundary.crs(), "OUTPUT": mism})
j = IdwJob(boundary, boundary.extent(), boundary.crs(), [(points, "argila")],
           50, 2, 100, 3, tmp, mism, "_m", cell_size=10)
r_m = run_idw_job(j, ctx, QgsProcessingFeedback())
lm = QgsVectorLayer(mism, "m", "ogr")
print("Mismatch:", [f.name() for f in lm.fields()], r_m["warnings"][:1])
if [f.name() for f in lm.fields()] != ["id", "argila"] or not any(("substituído" in w or "replaced" in w) for w in r_m["warnings"]):
    errors.append("an incompatible old file should be replaced with a warning")
lm = None

# existing grid chosen by the user (here: a 10 m grid covering a larger area)
big = processing.run("native:creategrid", {"TYPE": 2,
    "EXTENT": f"{X0-200},{X0+400},{Y0-200},{Y0+350} [EPSG:31982]", "HSPACING": 10, "VSPACING": 10,
    "HOVERLAY": 0, "VOVERLAY": 0, "CRS": boundary.crs(), "OUTPUT": "memory:"})["OUTPUT"]
job_e = IdwJob(boundary, boundary.extent(), boundary.crs(), [(points, "argila"), (points, "pH")],
               50, 2, 100, 3, tmp, os.path.join(tmp, "existing.shp"), "_e", grid_input=big)
r_e = run_idw_job(job_e, ctx, QgsProcessingFeedback())
lyr_e = check_result(r_e["output"], "existing grid")
# an existing grid chosen by the user keeps its own columns (only generated grids are cleaned)
if [f.name() for f in lyr_e.fields()][:5] != ["id", "left", "top", "right", "bottom"]:
    errors.append("an existing grid should keep its own columns")
if lyr_e.featureCount() >= big.featureCount():
    errors.append("only cells touching the field should be used from an existing grid")

# Regression (1.5.2): sensor passes with one wider gap and a short radius left empty pixels,
# and the 5 m cells over them came out blank in the final grid.
gap = QgsVectorLayer("Point?crs=EPSG:31982&field=CE:double", "ce_gap", "memory")
gfeats = []
for yy in [5, 20, 35, 50, 95, 110, 125, 140]:          # 45 m gap between y = 50 and y = 95
    for xx in range(-5, 206, 2):
        g2 = QgsFeature(gap.fields())
        g2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X0 + xx, Y0 + yy)))
        g2.setAttributes([2.0 + xx / 100.0 + yy / 200.0])
        gfeats.append(g2)
gap.dataProvider().addFeatures(gfeats)
i18n.set_language("pt")
job_g = IdwJob(boundary, boundary.extent(), boundary.crs(), [(gap, "CE")], 50, 2, 10, 5, tmp,
               os.path.join(tmp, "gap.shp"), "_g", cell_size=5)
r_g = run_idw_job(job_g, ctx, QgsProcessingFeedback())
lyr_g = QgsVectorLayer(r_g["output"], "g", "ogr")
blank = sum(1 for f in lyr_g.getFeatures() if f["CE"] is None or f["CE"] != f["CE"])
pct = r_g["layers"][0]["fallback_pct"]
print(f"Gap between passes: {blank} blank cells, fallback in {pct:.1f}% of the field,",
      "warning:", r_g["warnings"][:1])
if blank:
    errors.append(f"{blank} blank cells where the radius reached no sample")
if not (pct > 0 and r_g["warnings"] and "mais próximas" in r_g["warnings"][0]):
    errors.append("the final message should warn about the area that used the nearest samples")

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

# 1.8.0: before rewriting the standard grid, the wizard removes the layers that read it
# (they would lock the file on Windows) and loads the kept columns again afterwards
removed = idw_wizard.release_output(r["output"])
print("Released layers:", removed)
left_over = [l for l in QgsProject.instance().mapLayers().values()
             if l.source().split("|")[0] == r["output"]]
if len(removed) != 2 or left_over:
    errors.append("layers reading the standard grid should be removed before rewriting it")
_j = IdwJob(QgsProcessingFeatureSourceDefinition(boundary.id(), True),
            features_extent(boundary.getSelectedFeatures()), boundary.crs(),
            [(points, "pH")], 50, 2, 100, 3, tmp, r["output"], "_w", cell_size=10)
_r = run_idw_job(_j, ctx, QgsProcessingFeedback())
idw_wizard.load_results(_r, W)
idw_wizard.reload_previous(_r, removed)
names_now = sorted(l.name() for l in QgsProject.instance().mapLayers().values()
                   if l.source().split("|")[0] == r["output"])
print("After rerun:", _r["kept"], names_now)
if _r["kept"] != ["argila"] or not any(n == removed[0][0] for n in names_now if "argila" in n):
    errors.append("the layer of the kept column (argila) should be loaded again with its name")


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
infos = []
QMessageBox.information = staticmethod(lambda *a, **k: (infos.append(a[2]), QMessageBox.StandardButton.Ok)[1])
wz = idw_wizard.IdwWizard()
wz.show()
p1 = wz.currentPage()
p1.combo.setCurrentIndex(p1.combo.findData(boundary.id()))
p1.edit_folder.setText(tmp)
# 1.7.0: steps 1 and 2 show a fixed panel on the right explaining every option, and the
# Help button explains the concept of the step
def _check_panel(page, words, label):
    panel = getattr(page, "side_panel", None)
    if panel is None:
        errors.append(f"{label}: explanation panel on the right missing")
        return
    app.processEvents()
    text = panel.toPlainText()
    sizes = page.splitter.sizes()
    print(f"{label} panel:", text[:60].replace("\n", " "), "| sizes:", sizes)
    if any(w not in text for w in words):
        errors.append(f"{label}: panel should explain {words}")
    if page.splitter.indexOf(panel) != 1 or min(sizes) <= 0:
        errors.append(f"{label}: panel should be visible on the right side")
    # Regression: the wizard gave the page only its size hint and the panel stopped halfway
    print(f"{label} page height:", page.height(), "of", wz.height())
    if page.height() < 0.75 * wz.height():
        errors.append(f"{label}: the two sides should fill the page height")
_check_panel(p1, ["Camada de contorno", "Tolerância", "Grade vetorial", "Pasta de saída"], "Step 1")
from agriprecisa.i18n import tr as _tr
if "Efeito de borda" not in _tr("help_page1") or "Tolerância:" in _tr("help_page1"):
    errors.append("help of step 1 should explain the concept, not repeat the options")
shot_p1 = os.environ.get("AGRIPRECISA_SHOT_P1")
if shot_p1:
    app.processEvents(); wz.grab().save(shot_p1)
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
_check_panel(page, ["densidade", "EPSG", "seta"], "Step 2")
if "Densidade amostral" not in _tr("help_page2") or "seta" in _tr("help_page2"):
    errors.append("help of step 2 should explain the concept, not repeat the options")
shot_p2 = os.environ.get("AGRIPRECISA_SHOT_P2")
if shot_p2:
    app.processEvents(); wz.grab().save(shot_p2)
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

# 3c) Step 3: sliders, texts, spacing, neighbours, influence bars and live preview
from qgis.core import QgsSettings
for k in range(amostras.childCount()):
    amostras.child(k).setCheckState(0, Qt.CheckState.Checked)
wz.next()
p3 = wz.currentPage()
print("Step 3 page:", p3.title())
if hasattr(p3, "radio_advanced") or hasattr(p3, "spin_p"):
    errors.append("the standard layout should no longer exist in step 3")
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
# 1.6.0: the default radius reaches the 16 neighbours in 95 % of the field and the 4 everywhere,
# so step 3 opens without the orange warning
if p3.label_r_gap.isVisibleTo(p3) or p3.gap_percent() > 0:
    errors.append("default radius should reach the minimum of neighbours in the whole field")
if p3.radius_status()[0] != "ok":
    errors.append("default radius should not limit the maximum of neighbours")
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
# 1.6.0: weight curve removed; the preview fills the whole right column
if hasattr(p3, "curve"):
    errors.append("the weight curve should no longer exist in step 3")
_g = next(l for l in p3.scroll.widget().layout().children() if hasattr(l, "getItemPosition"))
_pos = _g.getItemPosition(_g.indexOf(p3.box_preview))
print("Preview position (row, col, rowspan, colspan):", _pos)
if _pos[1] != 1 or _pos[2] != 2:
    errors.append("the map preview should fill the whole right column")
if not p3.box_advanced.isCollapsed():
    errors.append("the search radius should start inside a collapsed 'Avançado' box")
# 1.7.0: the neighbours box (text and influence bars) was removed from step 3
if hasattr(p3, "bars") or hasattr(p3, "label_n"):
    errors.append("the 'Vizinhas por pixel' box should no longer exist in step 3")
# preview attribute selector
p3.combo_attr.setCurrentIndex(1)
p3.refresh_preview()
print("Preview attribute:", p3.combo_attr.currentText(), "| samples:", p3.preview.points[2].size)
if p3.preview.points[2].size != 19:
    errors.append("preview for pH should use the 19 non-empty samples")
p3.combo_attr.setCurrentIndex(0)
# each attribute keeps its own parameters
p3.slider_p.setValue(30)
p3.combo_attr.setCurrentIndex(1)                     # pH
if p3.slider_p.value() != 20 or p3.power() != 2.0:
    errors.append("pH should keep its own (default) P when argila changes")
p3.combo_attr.setCurrentIndex(0)                     # back to argila
if p3.slider_p.value() != 30:
    errors.append("argila lost its own P after switching attributes")
origins = [p3.table.item(r, 4).text() for r in range(p3.table.rowCount())]
print("Summary table:", [[p3.table.item(r, c).text() for c in range(5)] for r in range(p3.table.rowCount())])
if p3.table.item(0, 2).text() != "4 a 16":
    errors.append("summary table should show the neighbours (4 a 16)")
if origins != ["manual", "padrão"]:
    errors.append(f"origins should be manual / padrão, got {origins}")
p3.table.selectRow(1)
if p3.combo_attr.currentIndex() != 1:
    errors.append("clicking a summary row should select that attribute")
p3.combo_attr.setCurrentIndex(0)
p3.slider_p.setValue(20)
p3.refresh_preview()
app.processEvents()
cmp_dir = os.environ.get("AGRIPRECISA_SHOT_CMP")
if cmp_dir:
    for pv in (10, 30):
        p3.slider_p.setValue(pv)
        p3.refresh_preview()
        app.processEvents()
        p3.controls.parentWidget().grab().save(os.path.join(cmp_dir, f"p{pv}.png"))
    p3.slider_p.setValue(20)
    p3.refresh_preview()
shot3 = os.environ.get("AGRIPRECISA_SHOT3")
if shot3:
    wz.grab().save(shot3)
# slider ranges: P 0.5 to 5.0, radius 1x to 10x (the radius only limits computation now)
if (p3.slider_p.minimum(), p3.slider_p.maximum(), p3.slider_r.minimum(), p3.slider_r.maximum()) != (5, 50, 10, 100):
    errors.append("sliders should cover P 0.5-5.0 and radius 1x-10x")
p3.slider_p.setValue(45)                              # argila: P = 4,5 (beyond the old limit of 3)
p3.validatePage()
print("Wizard params:", wz.params, wz.param_origins, wz.pixel)
if len(wz.params) != 2 or wz.params[0][0] != 4.5 or wz.params[1][0] != 2.0 or wz.params[0][2] != 16:
    errors.append("wizard should hand one (P, radius, max neighbours) per attribute to the job")
wz.hide()

# 3d) Sensor passes (like EC): coverage distance and cross-validation
import math as _m
import numpy as _np
rng = _np.random.default_rng(7)
ce = QgsVectorLayer("Point?crs=EPSG:31982&field=CE:double&field=CE2:double", "ce_sensor", "memory")
cfeats = []
for yy in _np.arange(5, 150, 15.0):                  # passes every 15 m
    for xx in _np.arange(-5, 206, 2.0):              # points every 2 m along the pass
        f2 = QgsFeature(ce.fields())
        f2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(X0 + xx, Y0 + yy)))
        val = 2 + 0.01 * xx + 0.5 * _m.sin(yy / 30.0) + rng.normal(0, 0.05)
        val2 = _m.sin(xx / 6.0) * _m.cos(yy / 7.0) + rng.normal(0, 0.02)   # short-range
        f2.setAttributes([float(val), float(val2)])
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
item_ce.child(1).setCheckState(0, Qt.CheckState.Checked)
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
q3.select_attribute(0)
q3.run_cv_this()
if not dialogs:
    errors.append("cross-validation dialog not shown")
else:
    dlg = dialogs[-1]
    print("CV (CE):", dlg.result_summary)
    best_p = dlg.result_summary["power"]
    if abs(q3.slider_p.value() / 10.0 - best_p) > 1e-6:
        errors.append("'Aplicar' did not move the P slider to the suggested value")
    if q3.max_neighbours() != dlg.result_summary["max_neighbours"]:
        errors.append("'Aplicar' did not set the maximum of neighbours")
    if abs(q3.radius() - round(dlg.result_summary["radius"], 1)) > 1e-6:
        errors.append("'Aplicar' did not set the radius computed for the maximum")
    cols = [dlg.table.horizontalHeaderItem(c).text() for c in range(dlg.table.columnCount())]
    if cols[0] != "até 4\nvizinhas" or cols[-1] != "até 32\nvizinhas":
        errors.append(f"cross-validation columns should be the maximum of neighbours, got {cols}")
    if q3.table.item(0, 2).text() != f"4 a {q3.max_neighbours()}":
        errors.append("summary table should show the maximum chosen by the auto-fit")
    if q3.table.item(0, 4).text() != "automático" or q3.table.item(1, 4).text() != "padrão":
        errors.append("'Ajuste automático' must change only the selected attribute")
    # Regression: the suggested P (e.g. 0,6) was outside the rows of the table (P 1 to 3)
    rows_p = [dlg.table.verticalHeaderItem(r).text() for r in range(dlg.table.rowCount())]
    if rows_p[0] != "P = 0,5" or rows_p[-1] != "P = 5,0":
        errors.append(f"cross-validation table should cover P 0,5 to 5,0, got {rows_p}")
    shot_cv = os.environ.get("AGRIPRECISA_SHOT_CV")
    if shot_cv:
        dlg.show(); app.processEvents()
        if dlg.table.height() < dlg.table.minimumHeight():
            errors.append("cross-validation table is cut")
        dlg.grab().save(shot_cv); dlg.hide()
q3.run_cv_all()
print("CV all:", q3.last_cv_all)
st_ce, st_ce2 = (q3.state[k] for k in q3.keys)
print("Per attribute:", {q3.labels[k]: (q3.state[k]["power"], q3.state[k]["max_n"], q3.state[k]["radius"])
                         for k in q3.keys})
if [q3.table.item(r, 4).text() for r in range(2)] != ["automático", "automático"]:
    errors.append("'Ajuste automático para todos' should apply to every attribute")
if (st_ce["power"], st_ce["max_n"]) == (st_ce2["power"], st_ce2["max_n"]):
    errors.append("CE (smooth) and CE2 (short-range) should get different parameters")
if not infos or "CE2" not in infos[-1]:
    errors.append("summary message of 'Ajuste automático para todos' missing")
# step 3 warns when the radius does not reach samples in part of the field
q3.select_attribute(0)
q3.box_advanced.setCollapsed(False)
q3.slider_r.setValue(10)                               # 1x coverage: many pixels reach fewer than 4
print("Gap warning:", q3.label_r_gap.isVisibleTo(q3), q3.label_r_gap.text()[:70])
# Regression: the warning was drawn over the title of the collapsed 'Avançado' box
if q3.label_r_gap.parentWidget() is q3.box_advanced or q3.box_advanced.isAncestorOf(q3.label_r_gap):
    errors.append("the orange warning should stay outside the collapsible box")
q3.box_advanced.setCollapsed(True); app.processEvents()
if not q3.label_r_gap.isVisibleTo(q3):
    errors.append("the orange warning should stay visible with 'Avançado' collapsed")
q3.box_advanced.setCollapsed(False)
if not q3.label_r_gap.isVisibleTo(q3) or "mais próximas" not in q3.label_r_gap.text():
    errors.append("step 3 should warn when the radius leaves part of the field without samples")
q3.slider_r.setValue(40)
if q3.label_r_gap.isVisibleTo(q3):
    errors.append("warning should disappear when the radius covers the whole field")
# names of the buttons
if (q3.button_cv_this.text(), q3.button_cv_all.text()) != ("Ajuste automático", "Ajuste automático para todos"):
    errors.append("button texts should be 'Ajuste automático' / 'Ajuste automático para todos'")
q3.select_attribute(1)
q3.refresh_preview(); app.processEvents()
# the radius set by the auto-fit does not cut the maximum: the text must say so
print("Radius text after auto-fit:", q3.label_r_text.text()[:60])
if "O raio não limita" not in q3.label_r_text.text():
    errors.append("after the auto-fit the radius should be described as not limiting")
# Regression: right column (weight chart and bars) was cut when the content was wider than the window
if content.minimumSizeHint().width() > q3.scroll.viewport().width() + 1 if (content := q3.scroll.widget()) else False:
    errors.append("step 3 content wider than the default window")
# Regression: texts of step 3 overlapped when the content did not fit the window
content = q3.scroll.widget()
print("Step 3 content min height:", content.minimumSizeHint().height(), "| visible:", q3.scroll.viewport().height(),
      "| scrollbar:", q3.scroll.verticalScrollBar().isVisible())
for lbl in (q3.label_p_text, q3.label_r_text, q3.label_spacing):
    if lbl.height() < lbl.minimumHeight():
        errors.append("step 3 text squeezed below its minimum height")
shot4 = os.environ.get("AGRIPRECISA_SHOT4")
if shot4:
    wz2.grab().save(shot4)
wz2.hide()

class _Log(QgsProcessingFeedback):
    def __init__(self):
        super().__init__()
        self.lines = []
    def pushInfo(self, info):
        self.lines.append(info)
    def reportError(self, error, fatalError=False):
        self.lines.append("ERROR " + error)

i18n.set_language("pt")
log = _Log()
res_auto = processing.run("agriprecisa:idw_vector_grid", {
    "BOUNDARY": boundary, "POINTS": ce, "FIELDS": ["CE", "CE2"], "TOLERANCE": 50,
    "POWER": 2, "RADIUS": 0, "PIXEL": 5, "CELL_SIZE": 5, "AUTO_PARAMS": True,
    "RASTER_FOLDER": os.path.join(tmp, "auto"), "OUTPUT": os.path.join(tmp, "auto.gpkg")},
    feedback=log)
auto_lines = [l for l in log.lines if "validação cruzada" in l]
print("Processing auto:", auto_lines)
if len(auto_lines) != 2 or any(l.startswith("ERROR") for l in auto_lines):
    errors.append("Processing AUTO_PARAMS should cross-validate each field")
auto_grid = QgsVectorLayer(res_auto["OUTPUT"], "a", "ogr")
if not {"CE", "CE2"} <= {f.name() for f in auto_grid.fields()}:
    errors.append("Processing AUTO_PARAMS output missing mean fields")

QgsProject.instance().removeMapLayer(ce.id())
QgsProject.instance().removeMapLayer(geo.id())

# 3e) Step 1 default output folder: project subfolder, created on demand, then last used
from qgis.core import QgsSettings as _S
proj_dir = os.path.join(tmp, "projeto_aula")
os.makedirs(proj_dir, exist_ok=True)
QgsProject.instance().write(os.path.join(proj_dir, "aula.qgz"))
_S().remove("AgriPrecisa/last_output_folder")
w3 = idw_wizard.IdwWizard()
w3.show()
f1 = w3.currentPage()
expected = os.path.join(proj_dir, "AgriPrecisa")
print("Default folder:", f1.edit_folder.text(), "|", f1.label_folder.text())
if os.path.normpath(f1.edit_folder.text()) != os.path.normpath(expected):
    errors.append("default output folder should be <project>/AgriPrecisa")
f1.combo.setCurrentIndex(f1.combo.findData(boundary.id()))
f1.spin_cell.setValue(10)
print("Grid hint:", f1.label_grid.text())
if "talhao_Grade Padrão_10x10.shp" not in f1.label_grid.text():
    errors.append("step 1 should show the standard grid file name")
shot1 = os.environ.get("AGRIPRECISA_SHOT1")
if shot1:
    app.processEvents(); w3.grab().save(shot1)
w3.next()
if not os.path.isdir(expected):
    errors.append("AgriPrecisa subfolder was not created")
if w3.cell_size != 10 or w3.grid_layer is not None:
    errors.append("new grid with 10 m cells should be stored in the wizard")
w3.hide()

# existing grid in step 1: cell size estimated, pixel limited to the cell in step 3
QgsProject.instance().addMapLayer(big)
big.setName("grade_10m")
w7 = idw_wizard.IdwWizard()
w7.show()
e1 = w7.currentPage()
e1.combo.setCurrentIndex(e1.combo.findData(boundary.id()))
e1.edit_folder.setText(tmp)
e1.radio_grid_old.setChecked(True)
e1.combo_grid.setCurrentIndex(e1.combo_grid.findData(big.id()))
w7.next()
print("Existing grid:", w7.grid_layer.name() if w7.grid_layer else None, "cell", w7.cell_size)
if w7.grid_layer is None or abs(w7.cell_size - 10) > 1e-6:
    errors.append("existing grid: cell size should be estimated as 10 m")
e2 = w7.currentPage()
amo = e2.tree.findItems("amostras [EPSG:31982]", Qt.MatchFlag.MatchExactly, 0)[0]
amo.child(0).setCheckState(0, Qt.CheckState.Checked)
w7.next()
e3 = w7.currentPage()
print("Step 3 pixel:", e3.spin_px.value(), "max", e3.spin_px.maximum())
if e3.spin_px.value() != 10 or e3.spin_px.maximum() != 10:
    errors.append("pixel should start equal to the cell and never exceed it")
w7.hide()
QgsProject.instance().removeMapLayer(big.id())
chosen = os.path.join(tmp, "outra_pasta")
os.makedirs(chosen, exist_ok=True)
w4 = idw_wizard.IdwWizard()
w4.show()
g1 = w4.currentPage()
g1.edit_folder.setText(chosen)
g1.combo.setCurrentIndex(g1.combo.findData(boundary.id()))
w4.next()
w4.hide()
w5 = idw_wizard.IdwWizard()
w5.show()
h1 = w5.currentPage()
print("Next run folder:", h1.edit_folder.text(), "|", h1.label_folder.text())
if os.path.normpath(h1.edit_folder.text()) != os.path.normpath(chosen) or "Última" not in h1.label_folder.text():
    errors.append("next run should offer the last folder used")
w5.hide()
QgsProject.instance().setFileName("")
_S().remove("AgriPrecisa/last_output_folder")
w6 = idw_wizard.IdwWizard()
w6.show()
k1 = w6.currentPage()
print("Unsaved project:", repr(k1.edit_folder.text()), "|", k1.label_folder.text())
if k1.edit_folder.text() or "Salve o projeto" not in k1.label_folder.text():
    errors.append("unsaved project without history should leave the folder empty with a hint")
w6.hide()

# 3b) DTM and plant height in row crops (2.0.0)
import numpy as _np
from osgeo import gdal as _gdal, osr as _osr
from qgis.core import QgsRasterLayer, QgsProcessingException
from agriprecisa.core import paths as _paths
from agriprecisa.processing_provider.alg_dtm_rows import style_pseudocolor, style_plant_mask

_mdt_dir = tempfile.mkdtemp()
_n, _px = 240, 0.25
_yy, _xx = _np.mgrid[0:_n, 0:_n] * _px
_terrain = 600 + 0.05 * _xx + 0.3 * _np.sin(_yy / 15.0)
_rows = _np.mod(_xx, 3.6) < 1.6
_dsm = _terrain + _np.where(_rows, 2.0, 0.0)
_dsm[:, :8] = 0                      # clipped border stored as 0 (no data)
_dsm_path = os.path.join(_mdt_dir, "DSM.tif")
_ds = _gdal.GetDriverByName("GTiff").Create(_dsm_path, _n, _n, 1, _gdal.GDT_Float32)
_ds.SetGeoTransform((X0, _px, 0, Y0 + _n * _px, 0, -_px))
_srs = _osr.SpatialReference()
_srs.ImportFromEPSG(31982)
_ds.SetProjection(_srs.ExportToWkt())
_ds.GetRasterBand(1).WriteArray(_dsm[::-1])
_ds = None

_out = {k: os.path.join(_mdt_dir, n) for k, n in
        (("OUT_DTM", "MDT.tif"), ("OUT_HEIGHT", "Altura_plantas.tif"), ("OUT_MASK", "Mascara_planta.tif"))}
_params = dict(INPUT=_dsm_path, CROP=0, SPACING=0, FACTOR=1.5, RESOLUTION=0, TOLERANCE=0,
               ZERO_NODATA=True, **_out)
_r = processing.run("agriprecisa:dtm_row_crops", _params)


def _read(path):
    ds = _gdal.Open(path)
    arr = ds.GetRasterBand(1).ReadAsArray()[::-1]
    ds = None
    return arr


_h, _d, _m = _read(_r["OUT_HEIGHT"]), _read(_r["OUT_DTM"]), _read(_r["OUT_MASK"])
_c = (slice(30, -30), slice(40, -30))
_plant_h = float(_np.median(_h[_c][_rows[_c]]))
_dtm_err = float(_np.max(_np.abs(_d[_c] - _terrain[_c])))
print(f"DTM tool: plant height {_plant_h:.2f} m, DTM max error {_dtm_err:.3f} m, "
      f"mask values {sorted(set(_np.unique(_m)))}")
if abs(_plant_h - 2.0) > 0.15 or _dtm_err > 0.15:
    errors.append("DTM tool: terrain or plant height not recovered")
if not (_d[:, :8] == -9999).all() or not (_m[:, :8] == 255).all():
    errors.append("DTM tool: value 0 border should be no data")
if set(_np.unique(_m)) - {0, 1, 255}:
    errors.append("DTM tool: plant mask must hold only 0, 1 and no data")
# 2.1.1: plant mask, 1 = plant (rows), 0 = soil (inter-rows)
_mc, _rc = _m[_c], _rows[_c]
print(f"plant mask: {100 * (_mc[_rc] == 1).mean():.1f}% of row pixels = 1, "
      f"{100 * (_mc[~_rc] == 0).mean():.1f}% of inter-row pixels = 0")
if (_mc[_rc] == 1).mean() < 0.95 or (_mc[~_rc] == 0).mean() < 0.95:
    errors.append("DTM tool: plant mask must be 1 on plants and 0 on soil")

# Regression 2.0.0: output already loaded in QGIS (locked on Windows) made the run fail at the
# end ("Deleting MDT.tif failed: Permission denied"); it must be saved under a free name.
with mock.patch.object(_paths.os, "rename", side_effect=PermissionError("in use")):
    _r2 = processing.run("agriprecisa:dtm_row_crops", _params)
print("locked outputs saved as:", [os.path.basename(_r2[k]) for k in sorted(_r2)])
if os.path.basename(_r2["OUT_DTM"]) != "MDT_2.tif" or not os.path.isfile(_r2["OUT_DTM"]):
    errors.append("DTM tool: locked output was not redirected to MDT_2.tif")

# Same through the dialog path: outputs loaded into the project, styled, locked name redirected
_before = set(QgsProject.instance().mapLayers())
with mock.patch.object(_paths.os, "rename", side_effect=PermissionError("in use")):
    processing.runAndLoadResults("agriprecisa:dtm_row_crops", _params)
_new = [QgsProject.instance().mapLayer(i) for i in set(QgsProject.instance().mapLayers()) - _before]
_loaded = {os.path.basename(l.source()): l.renderer().type() for l in _new}
print("loaded:", _loaded)
if _loaded.get("MDT_3.tif") != "singlebandpseudocolor" or _loaded.get("Mascara_planta_3.tif") != "paletted":
    errors.append("DTM tool: loaded outputs not redirected or not styled")
QgsProject.instance().removeMapLayers([l.id() for l in _new])

# Custom crop without spacing: clear error
try:
    processing.run("agriprecisa:dtm_row_crops", dict(_params, CROP=7))
    errors.append("DTM tool: custom crop without spacing should fail")
except QgsProcessingException as e:
    print("custom crop without spacing ->", str(e)[:60])

# Window too small: soybean spacing with a coarse resolution
try:
    processing.run("agriprecisa:dtm_row_crops", dict(_params, CROP=3, RESOLUTION=0.5))
    errors.append("DTM tool: too small window should fail")
except QgsProcessingException as e:
    print("too small window ->", str(e)[:60])

# Styles applied when the layers are loaded
_lh = QgsRasterLayer(_r["OUT_HEIGHT"], "h")
style_pseudocolor(_lh, 0.0, 2.0, "Viridis")
_lm = QgsRasterLayer(_r["OUT_MASK"], "m")
style_plant_mask(_lm)
_cls = {c.value: c.label for c in _lm.renderer().classes()}
print("plant mask classes:", _cls)
if _cls != {1: i18n.tr("mdt_class_plants"), 0: i18n.tr("mdt_class_soil")}:
    errors.append("DTM tool: plant mask style must show 1 = plants, 0 = soil")
print("styles:", _lh.renderer().type(), _lm.renderer().type())
if _lh.renderer().type() != "singlebandpseudocolor" or _lm.renderer().type() != "paletted":
    errors.append("DTM tool: styles not applied")

# 2.2.0: plant polygons, slope and plant height parameters, optional outputs
_r3 = processing.run("agriprecisa:dtm_row_crops", dict(
    _params, SLOPE=0, PLANT_HEIGHT=0.5, OUT_POLYGONS=os.path.join(_mdt_dir, "Poligonos.shp"),
    OUT_DTM=None))
_pg = QgsVectorLayer(_r3["OUT_POLYGONS"], "pg", "ogr")
_pg_names = [f.name() for f in _pg.fields()]
_pg_area = sum(f["area_m2"] for f in _pg.getFeatures())
_mask_area = float((_read(_r3["OUT_MASK"]) == 1).sum()) * 0.25 * 0.25
print(f"plant polygons: {_pg.featureCount()} polygons, {_pg_area:.1f} m2 (mask {_mask_area:.1f} m2), fields {_pg_names}")
if _pg_names != ["id", "area_m2", "alt_media", "alt_max"] or abs(_pg_area - _mask_area) > 0.01:
    errors.append("plant polygons: fields or area do not match the plant mask")
_geom_area = sum(f.geometry().area() for f in _pg.getFeatures())
if abs(_geom_area - _mask_area) > 0.01:
    errors.append("plant polygons: geometry area differs from the mask")
# synthetic field: one polygon per hedge row (16 or 17 rows, the 2 m no-data border aside)
if not (15 <= _pg.featureCount() <= 17):
    errors.append("plant polygons: one polygon per hedge expected")
if "OUT_DTM" in _r3:
    errors.append("DTM tool: unchecked DTM output should not be created")

# Wizard (2.2.0)
from agriprecisa.gui import mdt_wizard as _mw
from qgis.PyQt.QtWidgets import QWizard as _QW
_dsm_layer = QgsRasterLayer(_dsm_path, "DSM_teste")
_rgb_path = os.path.join(_mdt_dir, "RGB.tif")
_rgb_arr = _np.where(_rows, 1, 0)
_rds = _gdal.GetDriverByName("GTiff").Create(_rgb_path, _n, _n, 3, _gdal.GDT_Byte)
_rds.SetGeoTransform((X0, _px, 0, Y0 + _n * _px, 0, -_px))
_rds.SetProjection(_srs.ExportToWkt())
for _b, (_on, _off) in enumerate(((40, 150), (140, 110), (40, 80))):
    _rds.GetRasterBand(_b + 1).WriteArray(_np.where(_rgb_arr, _on, _off)[::-1].astype("uint8"))
_rds = None
_rgb_layer = QgsRasterLayer(_rgb_path, "RGB_teste")
QgsProject.instance().addMapLayers([_dsm_layer, _rgb_layer])
_shot_dir = os.environ.get("AGRIPRECISA_MDT_SHOT")
_wz = _mw.MdtWizard(main)
_wz.resize(1140, 820)
_wz.show()
app.processEvents()

# Regression 2.2.0: on a small (or second) monitor the wizard could not shrink and the
# Back/Next/Cancel buttons were pushed off the window.
if _wz.minimumHeight() > 480 or _wz.minimumWidth() > 600:
    errors.append("wizard: minimum size too large for small screens")
def _check_buttons(step):
    """Buttons stay inside the window when it is made small (regression 2.2.0)."""
    _wz.resize(620, 450)
    app.processEvents()
    for _btn in (_QW.WizardButton.NextButton, _QW.WizardButton.FinishButton, _QW.WizardButton.CancelButton):
        _b = _wz.button(_btn)
        if _b.isVisible() and _b.mapTo(_wz, _b.rect().bottomRight()).y() > _wz.height():
            errors.append(f"wizard step {step}: buttons outside the window at 620x450")
    if _wz.height() > 470:
        errors.append(f"wizard step {step}: window could not shrink to 450 px ({_wz.height()})")
    _wz.resize(1140, 820)
    app.processEvents()


_p1 = _wz.currentPage()
_p1.combo_dsm.setLayer(_dsm_layer)
app.processEvents()
_check_buttons(1)

# Step 1: resolution from the DSM, RGB optional, measuring and automatic detection
if abs(_p1.spin_res.value() - 0.25) > 1e-9:
    errors.append("wizard step 1: working resolution should start at the DSM pixel")
if _p1.spin_spacing.value() != 0:
    errors.append("wizard step 1: spacing should start empty (to be measured)")
if _p1.view.image is None or _p1.overview.image is None:
    errors.append("wizard step 1: window or miniature not shown")
_cx, _cy = _wz.centre
_p1.spin_n.setValue(4)
_p1.view.add_point(_cx - 7.2, _cy)                 # 4 inter-rows of 3.6 m apart
_p1.view.add_point(_cx + 7.2, _cy)
print("wizard step 1 measured:", _p1.spin_spacing.value(), "|", _p1.label_measure.text()[:60])
if abs(_p1.spin_spacing.value() - 3.6) > 1e-6:
    errors.append("wizard step 1: measurement does not fill the spacing")
_p1.spin_spacing.setValue(0)
_p1.detect()
print("wizard step 1 detected:", _p1.spin_spacing.value(), "rows drawn:", len(_p1.view.rows))
if abs(_p1.spin_spacing.value() - 3.6) > 0.05 or not _p1.view.rows:
    errors.append("wizard step 1: automatic detection failed")
if "a 0° do norte" not in _p1.label_measure.text():               # north-south rows: 0, not 180
    errors.append(f"wizard step 1: row azimuth text {_p1.label_measure.text()}")
if "cerca de 57.600" not in _p1.label_info.text():                # 60 x 60 m at 0.25 m
    errors.append("wizard step 1: pixel count of the DSM")
_p1.combo_rgb.setLayer(_rgb_layer)
app.processEvents()
if _wz.source.rgb is None or abs(_p1.spin_spacing.value() - 3.6) > 0.05:
    errors.append("wizard step 1: RGB layer not used or spacing lost")
# 2.2.1: zoom (smaller window read again at full resolution), wheel and drag to pan
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtCore import QPoint
_p1.zoom_bar.button_in.click()
app.processEvents()
_ext1 = _p1.view.extent
print("zoom 1:", _wz.window_side, "m, image", _p1.view.image.width(), "px, label", _p1.zoom_bar.label.text())
if _wz.window_side != 15.0 or abs((_ext1[2] - _ext1[0]) - 15.0) > 1e-9 or _p1.view.image.width() != 60:
    errors.append("wizard zoom: step 1 window not 15 m at full resolution")
if abs((_p1.overview.window[2] - _p1.overview.window[0]) - 15.0) > 1e-9 or "15 x 15" not in _p1.zoom_bar.label.text():
    errors.append("wizard zoom: red square or label not updated")
_p1.view.wheeled.emit(1)
if _wz.window_side != 7.5:
    errors.append("wizard zoom: mouse wheel")
for _i in range(5):
    _p1.zoom_bar.button_in.click()
if _wz.window_side != 3.75 or _p1.zoom_bar.button_in.isEnabled():
    errors.append("wizard zoom: should stop at 3.75 m")
_c0 = _wz.centre
_r = _p1.view.image_rect()
_mid = QPoint(int(_r.center().x()), int(_r.center().y()))
QTest.mousePress(_p1.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _mid)
QTest.mouseMove(_p1.view, _mid + QPoint(40, 0))
QTest.mouseRelease(_p1.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _mid + QPoint(40, 0))
app.processEvents()
_shift = _c0[0] - _wz.centre[0]
_expected = 40 / _r.width() * 3.75
print(f"drag: centre moved {_shift:.3f} m west (expected {_expected:.3f}), points {_p1.view.points}")
if abs(_shift - _expected) > 0.05 or abs(_wz.centre[1] - _c0[1]) > 0.05 or _p1.view.points:
    errors.append("wizard drag: should pan the window and not measure")
QTest.mouseClick(_p1.view, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, _mid)
if len(_p1.view.points) != 1:
    errors.append("wizard click: a click (no drag) should still add a measuring point")
_p1.clear_measure()
for _i in range(5):
    _p1.zoom_bar.button_out.click()
_p1.move_window(*_c0)
if _wz.window_side != 30.0 or _p1.zoom_bar.button_out.isEnabled():
    errors.append("wizard zoom: should go back to 30 m")
if _shot_dir:
    _p1.detect()
    app.processEvents()
    _wz.grab().save(os.path.join(_shot_dir, "mdt_etapa1.png"))
_wz.next()

# Step 2: DTM preview, profile and sliders
_p2 = _wz.currentPage()
app.processEvents()
_check_buttons(2)
_pv = _wz.preview
_err_dtm = float(_np.nanmedian(_np.abs(_pv.c_dtm - _np.nanmedian(_pv.c_dtm))))
print(f"wizard step 2: soil {_pv.soil_pct:.1f}%, slope used {_pv.slope_used:.1f}%, profile points {len(_p2.profile.dsm)}")
# Regression 2.2.1: the margin was not a whole number of pixels and the preview came out one
# pixel short (59 instead of 60 at 15 m), so the mask could be shifted against the image
if _pv.c_dsm.shape != (120, 120):
    errors.append(f"wizard step 2: preview of 30 m at 0.25 m should be 120 px, got {_pv.c_dsm.shape}")
if _p2.view_dtm.image is None or _p2.profile.dsm is None or not (40 < _pv.soil_pct < 75):
    errors.append("wizard step 2: DTM preview not computed")
# the DTM preview has no plants: height of the rows about 2 m
_hrow = _np.nanmedian(_pv.c_height[_pv.c_valid & ~_pv.c_soil])
if abs(_hrow - 2.0) > 0.2:
    errors.append(f"wizard step 2: preview plant height {_hrow:.2f} m")
_p2.slider_slope.setValue(20)
if "20" not in _p2.labels["slope"].text() or "informada" not in _p2.texts["slope"].text():
    errors.append("wizard step 2: slope slider not applied")
_p2.slider_slope.setValue(0)
if "automática" not in _p2.texts["slope"].text():
    errors.append("wizard step 2: automatic slope text")
_p2.slider_tol.setValue(80)
if "alta" not in _p2.texts["tol"].text():
    errors.append("wizard step 2: tolerance text")
_p2.slider_tol.setValue(25)
_p2.slider_factor.setValue(10)
if "estreita" not in _p2.texts["factor"].text():
    errors.append("wizard step 2: factor text")
_p2.slider_factor.setValue(15)
_p2.zoom_bar.button_in.click()
app.processEvents()
print("zoom step 2:", _wz.preview.c_dsm.shape, "extent", round(_p2.view_dsm.extent[2] - _p2.view_dsm.extent[0], 2))
if _wz.preview.c_dsm.shape != (60, 60) or abs(_p2.view_dtm.extent[2] - _p2.view_dtm.extent[0] - 15) > 1e-9:
    errors.append("wizard zoom: step 2 preview not recomputed for 15 m")
_p2.zoom_bar.button_out.click()
app.processEvents()
if _shot_dir:
    _wz.grab().save(os.path.join(_shot_dir, "mdt_etapa2.png"))
_wz.next()

# Step 3: plant mask over the RGB, minimum height and transparency
_p3 = _wz.currentPage()
app.processEvents()
_check_buttons(3)
_ov = _p3.view.overlay
if _p3.view.image is None or _ov is None:
    errors.append("wizard step 3: mask preview not shown")
_txt0 = _p3.label_numbers.text()
_p3.slider_h.setValue(50)                        # 2.50 m: above the hedges, no plants
_txt1 = _p3.label_numbers.text()
print("wizard step 3:", _txt0[:70], "||", _txt1[:70])
if "<b>0" not in _txt1 or _txt0 == _txt1:
    errors.append("wizard step 3: minimum height does not change the mask")
_p3.slider_h.setValue(6)
# 2.2.1: zoom and outline
_p3.zoom_bar.button_in.click()
_p3.zoom_bar.button_in.click()                   # 7.5 m
app.processEvents()
if _p3.view.overlay.width() != 30 or _p3.background.width() != 30 or abs(_p3.view.extent[2] - _p3.view.extent[0] - 7.5) > 1e-9:
    errors.append("wizard zoom: step 3 mask and image not at 7.5 m")


def _opaque(img):
    return sum(1 for _y in range(img.height()) for _x in range(img.width()) if img.pixelColor(_x, _y).alpha() > 0)


_fill_px = _opaque(_p3.view.overlay)
_p3.combo_mode.setCurrentIndex(1)
app.processEvents()
_line_px = _opaque(_p3.view.overlay)
_col = next((_p3.view.overlay.pixelColor(_x, _y) for _y in range(30) for _x in range(30)
             if _p3.view.overlay.pixelColor(_x, _y).alpha() > 0), None)
print(f"mask fill {_fill_px} px, outline {_line_px} px, outline colour {_col.name() if _col else None}")
if not (0 < _line_px < _fill_px) or _col is None or _col.name() != "#ffdc00":
    errors.append("wizard step 3: outline mode")
if not _wz.mask_outline:
    errors.append("wizard step 3: outline choice not kept")
if _shot_dir:
    _wz.grab().save(os.path.join(_shot_dir, "mdt_etapa3_zoom_contorno.png"))
_p3.combo_mode.setCurrentIndex(0)
_p3.zoom_bar.button_out.click()
_p3.zoom_bar.button_out.click()
app.processEvents()
_p3.slider_alpha.setValue(18)                    # 90 percent transparent
if _p3.label_alpha.text() != "90%":
    errors.append("wizard step 3: transparency not applied")
app.processEvents()
if _shot_dir:
    _p3.slider_alpha.setValue(10)
    app.processEvents()
    _wz.grab().save(os.path.join(_shot_dir, "mdt_etapa3.png"))
_wz.next()

# Step 4: outputs with path and name, all on by default
_p4 = _wz.currentPage()
app.processEvents()
_check_buttons(4)
_paths = {k: _p4.files[k].filePath() for k in _p4.files}
print("wizard step 4 defaults:", {k: os.path.basename(v) for k, v in _paths.items()})
if not all(c.isChecked() for c in _p4.checks.values()):
    errors.append("wizard step 4: outputs should all be on by default")
_folder4 = os.path.join(_mdt_dir, "wizard")
for _k, _name in (("OUT_DTM", "DSM_teste_MDT.tif"), ("OUT_HEIGHT", "DSM_teste_Altura.tif"),
                  ("OUT_MASK", "DSM_teste_Mascara_planta.tif"), ("OUT_POLYGONS", "DSM_teste_Poligonos_planta.shp")):
    if os.path.basename(_paths[_k]) != _name:
        errors.append(f"wizard step 4: default name of {_k}")
    _p4.files[_k].setFilePath(os.path.join(_folder4, _name))
_p4.files["OUT_HEIGHT"].setFilePath(os.path.join(_folder4, "minha_altura"))   # no extension
_p4.checks["OUT_DTM"].setChecked(False)
if _p4.files["OUT_DTM"].isEnabled():
    errors.append("wizard step 4: unchecked output should disable its path")
if _shot_dir:
    _p4.checks["OUT_DTM"].setChecked(True)
    _wz.grab().save(os.path.join(_shot_dir, "mdt_etapa4.png"))
    _p4.checks["OUT_DTM"].setChecked(False)
if not _p4.validatePage():
    errors.append("wizard step 4: valid outputs rejected")
if set(_wz.outputs) != {"OUT_HEIGHT", "OUT_MASK", "OUT_POLYGONS"} or not _wz.outputs["OUT_HEIGHT"].endswith("minha_altura.tif"):
    errors.append(f"wizard step 4: outputs {_wz.outputs}")
_fb = _mw._LogFeedback()
_res = _mw.run_mdt_job(_wz, _fb)
_grp = QgsProject.instance().layerTreeRoot().findGroup(i18n.tr("mdt_group_name"))
_kids = [n.layer() for n in _grp.findLayers()] if _grp else []
print("wizard loaded:", [(l.name().split(" | ")[1], l.renderer().type()) for l in _kids])
if len(_kids) != 3 or os.path.exists(os.path.join(_folder4, "DSM_teste_MDT.tif")):
    errors.append("wizard: results not loaded or unchecked output created")
print("wizard log:", [ln for ln in _fb.lines if "Declividade" in ln or "Polígonos" in ln])
# second run with the layers open: released and replaced, no _2 names
_res2 = _mw.run_mdt_job(_wz, _mw._LogFeedback())
if os.path.basename(_res2["OUT_MASK"]) != "DSM_teste_Mascara_planta.tif" or len(_grp.findLayers()) != 3:
    errors.append("wizard: second run should replace the previous layers")
_wz.hide()

# Regression 2.0.1: choosing a crop did not show its values in the dialog (fields stayed at 0).
import qgis.utils as _qu
_qu.iface = iface
from processing.gui.AlgorithmDialog import AlgorithmDialog
_alg = QgsApplication.processingRegistry().createAlgorithmById("agriprecisa:dtm_row_crops")
_dlg = AlgorithmDialog(_alg, False, main)
_wr = _dlg.mainWidget().wrappers


def _vals():
    return tuple(round(float(_wr[k].parameterValue()), 3) for k in ("SPACING", "RESOLUTION", "TOLERANCE"))


print("dialog opens with:", _vals())
if _vals()[:3] != (3.6, 0.25, 0.25):
    errors.append(f"crop list: dialog should open with the coffee values, got {_vals()}")
_combo = _wr["CROP"].combobox
_combo.setCurrentIndex(3)                       # soybean
print("soybean:", _vals())
if _vals() != (0.5, 0.1, 0.1):
    errors.append(f"crop list: soybean values not filled, got {_vals()}")
_wr["SPACING"].setParameterValue(0.45, QgsProcessingContext())
_combo.setCurrentIndex(7)                       # custom keeps the current values
print("custom:", _vals())
if _vals() != (0.45, 0.1, 0.1):
    errors.append(f"crop list: Custom should keep the current values, got {_vals()}")
_combo.setCurrentIndex(1)                       # citrus overwrites
if _vals() != (6.5, 0.25, 0.3):
    errors.append(f"crop list: citrus values not filled, got {_vals()}")
_wr["INPUT"].setParameterValue(_dsm_path, QgsProcessingContext())
_run_params = _dlg.mainWidget().createProcessingParameters()
print("parameters sent:", {k: _run_params[k] for k in ("CROP", "SPACING", "TOLERANCE")})
if _run_params["CROP"] != 1 or abs(_run_params["SPACING"] - 6.5) > 1e-9:
    errors.append("crop list: dialog parameters not passed to the algorithm")
_dlg.close()

# 4) Plugin load/unload through classFactory
import agriprecisa
QgsApplication.processingRegistry().removeProvider(provider)
plg = agriprecisa.classFactory(iface)
plg.initGui()
reg = QgsApplication.processingRegistry().providerById("agriprecisa") is not None
_raster_menu = [c.args[1].text() for c in iface.addPluginToRasterMenu.call_args_list]
print("raster menu:", _raster_menu)
if not any("MDT" in t for t in _raster_menu):
    errors.append("DTM tool not added to the Raster menu")
if QgsApplication.processingRegistry().algorithmById("agriprecisa:dtm_row_crops") is None:
    errors.append("DTM algorithm not registered")
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
