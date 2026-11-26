# Changelog

## 2.2.1 (2026)
- *DTM and plant height* wizard, steps 1, 2 and 3: **zoom** with + and − buttons or the mouse wheel over the image. The window shrinks to 30, 15, 7.5 and 3.75 m and is read again at the original resolution (no pixelation); the DTM preview and the plant mask are recomputed for the smaller window. **Drag the image** to move the window; the red square on the miniature follows. The automatic spacing detection always uses a 30 m window.
- Step 3: the plant mask can be shown as **fill** (translucent green) or **outline** (yellow edge of the plant patches), which keeps the image visible when green plants are under a green mask.
- Fix: the margin around the preview window was not a whole number of pixels, so the preview could come out one pixel short (59 instead of 60) and the mask was slightly shifted against the image. Margin and window now follow the pixel grid. Regression test in the integration test (30 m and 15 m windows).
- Help texts reviewed in the three languages (zoom and outline explained in the Help of steps 1, 2 and 3).

## 2.2.0 (2026)
- *DTM and plant height* wizard redesigned (Raster > AgriPrecisa):
  1. **DSM, RGB and spacing**: optional RGB image (shown in the windows; without it the DSM is shown in grey); the working resolution starts at the DSM pixel, with the number of pixels to process and a warning for very large rasters; the crop list was removed. The **row spacing is measured on a 30 x 30 m window** (miniature of the field to move it): click the centre of a row and of another row a few rows away, enter how many inter-rows lie between them, and the spacing (distance divided by that number) fills the field; or **Detect automatically**, which finds the repeating pattern of the rows in the DSM and draws the detected rows (dashed yellow lines) for checking, with their azimuth.
  2. **DTM adjustment**: DSM of the window, DTM preview with the same grey scale and a **profile across the rows** (DSM and DTM lines); sliders for the window factor, the soil tolerance and the **slope** (0 = automatic); texts that change with each value.
  3. **Plant mask**: translucent mask over the RGB image (or the DSM) of the window, sliders for the **minimum plant height** and the **transparency**; plant cover, number of polygons and mean height in the window.
  4. **Output layers**: DTM, plant height, plant mask and **plant polygons**, each with a check box and its own path and file name (QGIS file widget), all on by default in the project folder with the DSM name.
- **Slope correction** (Processing parameter *Terrain slope*, 0 = automatic): the soil tolerance is raised by slope x half window, after the progressive morphological filter (Zhang et al., 2003), so that soil on crests, terrace edges and slope breaks is not lost. The automatic slope comes from the opening surface, taking the steepest value within the window; the log reports the median.
- **Plant mask by height**: 1 where the plant height is at least the *Minimum plant height* (default 0.30 m), 0 elsewhere (before it was the complement of the soil classification).
- **Plant polygons** (new output, Shapefile): one polygon per continuous patch of the plant mask, with `id`, `area_m2`, `alt_media` and `alt_max`; all patches kept.
- All outputs of the Processing algorithm are optional.
- **Removed**: height statistics per row segment and per plant (outputs, parameters and `core/mdt_stats.py`).
- **Fix**: on a small or second monitor the wizard could not shrink below a large minimum size and its Back, Next and Cancel buttons were pushed off the window. Pages now scroll, the minimum size is small and the window fits the screen when it opens. Regression test: the integration test shrinks every step to 620 x 450 and checks the buttons.
- Tests for the slope correction (ridge), the spacing detection (several angles and spacings) and the plant patches; the integration test drives the new wizard (measuring, detection, RGB, sliders, outputs with custom names, unchecked outputs) and saves screenshots with `AGRIPRECISA_MDT_SHOT=folder`.
- Help texts reviewed in the three languages; new Help for each step and updated Processing help.

## 2.1.1 (2026)
- *DTM and plant height*: the **soil mask became a plant mask**: layer *Plant mask (1 = plant, 0 = soil)*, file `[DSM]_Mascara_planta.tif` (Processing default `Mascara_planta.tif`). **The values are inverted** compared with versions 2.0.0 to 2.1.0 (which wrote 1 = soil): update raster calculator expressions or models that used the old mask. No data stays 255; colours unchanged (green plants, brown soil).
- The wizard step 2 preview is now called *Plant mask of the window*, with the legend green = plant (1), brown = soil (0).
- Tests: the integration test checks that the mask is 1 on the plant rows and 0 in the inter-rows, the style classes and the new file name.
- Help texts reviewed in the three languages (mask renamed everywhere).

## 2.1.0 (2026)
- **Wizard** for *DTM and plant height* (Raster > AgriPrecisa and toolbar), in the layout of the IDW wizard:
  1. DSM, crop, row spacing and working resolution, with CRS, pixel, recommended resolution and window size; explanation panel on the right.
  2. **Live soil mask preview**: miniature of the whole DSM; a click moves a 30 m window (at least 6 row spacings); side by side the DSM and the soil mask of the window; **sliders for the soil tolerance and the window factor** with explanations that change with the value (low, intermediate, high), soil percentage, window size and approximate plant height.
  3. Statistics (per row segment, per plant, crowns) and output folder (last folder or project folder), with the list of files that will be created (prefixed with the DSM name).
  4. Summary. Results are loaded and styled in the *DTM and plant height* group; layers of a previous run with the same files are released and replaced (no `_2` names); the final message repeats the key numbers of the log.
- **Height per row segment** (`Trechos_linhas.shp`): row direction and spacing detected from the plant pattern (log shows the azimuth and the measured spacing); each row cut into segments (default 5 m) with `alt_media`, `alt_p95`, `alt_max`, `cobert_pct`, `falha_m` (stretches without plants between plants, longer than twice the plant distance; headlands do not count) and `compr_m`.
- **Per plant**: tops (`Topos_plantas.shp`, points) and crowns (`Copas_plantas.shp`, polygons) with `alt_max`, `alt_media`, `area_m2`, `diam_m`; minimum distance between tops per crop (0 = crop value), filled by the crop list.
- Processing algorithm: new parameters *Length of the row segments* and *Minimum distance between plant tops*, and the three new optional outputs; vector outputs open in QGIS are also saved under a free name.
- Pure math in `core/mdt_stats.py`, unit-tested on synthetic orchards (rotated rows, missing plants, headlands); integration test drives the wizard (crop, preview, sliders, click, outputs, second run) and saves screenshots with `AGRIPRECISA_MDT_SHOT=folder`.
- Help texts reviewed in the three languages; new Help for each wizard step and updated Processing help.

## 2.0.1 (2026)
- Fix: in the *DTM and plant height in row crops* dialog, choosing a crop did not show its suggested values; the fields stayed at 0. The crop list now fills in row spacing, working resolution and soil tolerance as soon as it changes (and when the dialog opens), and the values can still be adjusted before running. *Custom* keeps the current values. Built on the generic Processing widget wrapper, so it works on QGIS 3 and QGIS 4.
- In batch mode and in the Model Designer, 0 in a field still means "use the crop value".
- Regression tests: `crop_field_values` in `tests/test_mdt_math.py`, and the integration test opens the real Processing dialog, switches crops and checks the fields and the parameters sent to the algorithm.
- Help texts reviewed in the three languages; the DTM help explains the automatic filling.

## 2.0.0 (2026)
- New tool **DTM and plant height in row crops (from the DSM)**: Raster > AgriPrecisa, toolbar button and Processing Toolbox (AgriPrecisa > Elevation models). Generalizes the coffee script to any crop planted in rows with visible soil in the inter-rows.
- Crop list (coffee, citrus, maize, soybean, sugarcane, grapevine, eucalyptus, custom) fills in suggested row spacing, working resolution and soil tolerance; any field set to a value other than 0 overrides the crop value.
- Outputs: DTM, plant height and soil mask (1 = soil, 0 = plants), loaded with colour ramps (Spectral for the DTM, Viridis for the height, green and brown for the mask).
- Teaching messages in the log: values used, window size in pixels and metres, soil percentage, plant height (mean, 95th percentile and maximum over plant pixels only); warnings for coarse resolution, finer resolution than the DSM, too small window, little or too much soil.
- Fix: an output file already loaded in QGIS (Windows) made the run fail at the end with "Permission denied"; the result is now saved under a free name (`MDT_2.tif`) with a warning. Regression tests in `tests/test_paths.py` and in the integration test.
- Pure math in `core/mdt_math.py`, unit-tested with a synthetic sloped field with plant rows.
- Help texts reviewed in the three languages; new Processing help for the DTM tool.

## 1.8.3 (2026)
- Fix: the Qt6 compatibility check of plugins.qgis.org flagged 10 enum names in `core/compat.py` written in the short form (for example `QgsWkbTypes.PointGeometry`); they now use the scoped form (`QgsWkbTypes.GeometryType.PointGeometry`), valid on QGIS 3 and QGIS 4. Same behaviour for the user.
- New regression test that requires the scoped form for every constant in `core/compat.py`.
- Help texts reviewed in the three languages (no changes needed).

## 1.8.2 (2026)
- Fix: the security scan (Bandit) of plugins.qgis.org blocked version 1.8.1 because of two empty error handlers (`try/except` followed by `pass` or `continue`) in `i18n.py` and `gui/idw_wizard.py`; they now set a value explicitly, with the same behaviour for the user.
- New regression test that forbids empty error handlers in the plugin code.
- Help texts reviewed in the three languages (no changes needed).

## 1.8.1 (2026)
- Fix: plugins.qgis.org rejected the package ("'%' must be followed by '%' or '('") because of a percent sign in the changelog of `metadata.txt`; the text was reworded.
- New regression test that reads every field of `metadata.txt` with the same parser as the QGIS repository.
- Help texts reviewed in the three languages (no changes needed).

## 1.8.0 (2026)
- Single result file: `[boundary]_Grade Padrão_[cell]x[cell].shp` now holds the cells clipped by the field, the ID and one column per attribute. The separate `[boundary]_IDW_[cell]x[cell]_[date]_[time].shp` file is no longer created.
- Running again with the same field and cell size adds the new columns to the standard grid and keeps the previous ones (matched by ID); attributes computed again are replaced. Layers of the previous run are reloaded with their names and styles. The "Reuse / Overwrite" question was removed.
- The generated grid keeps only the ID column, numbered 1, 2, 3..., before the zonal statistics (left, top, right, bottom and the original id of the grid tool are removed). An existing grid chosen by the user keeps its own columns.
- Processing toolbox: single output, the standard grid saved in the output folder (the separate output parameter was removed).
- Help texts reviewed in the three languages.

## 1.7.0 (2026)
- Steps 1 and 2 are split in two: the options on the left and, on the right, a fixed panel explaining every option (like the help panel of the Processing dialogs). The two sides can be resized.
- The Help button of steps 1 and 2 now explains the concept behind the step (area of interest, edge effect, management cell, sampling density, spatial dependence).
- Step 3: the "Neighbours per pixel" box with the influence bars was removed; the maximum of neighbours of each attribute stays in the summary table and the explanation of the neighbour rule is a link inside the "Advanced" box.
- Help texts reviewed in the three languages.

## 1.6.0 (2026)
- Minimum and maximum of neighbours per pixel, as in GIS interpolators (Surfer, ArcGIS, SAGA): every pixel uses at least 4 samples, even beyond the search radius, and at most the maximum (default 16), the nearest ones. The search radius now only saves computation in very dense sampling.
- Auto-fit: the cross-validation table now crosses P with the maximum of neighbours (4 to 32); the search radius is computed so it reaches the chosen maximum in 95% of the field.
- Step 3: the weight curve was removed and the map preview fills the whole right column; the neighbours (with the influence bars of the neighbours actually used) are shown below the power; the search radius moved to a collapsed "Advanced" box with a new explanation; the summary table shows the neighbours of each attribute.
- Processing toolbox: new "Minimum of neighbours" and "Maximum of neighbours" parameters; auto-fit chooses P and the maximum.
- Help texts reviewed in the three languages.

## 1.5.2 (2026)
- Fix: pixels that the search radius did not reach (for example, a wider gap between sensor passes near the border) were left without value, and the grid cells over them came out blank. These pixels now use the 4 nearest samples (regression tests).
- Step 3 shows an orange warning with the % of the field the radius does not reach; the final message reports it per attribute.
- Help texts reviewed.

## 1.5.1 (2026)
- Help updated: step 1 (vector grid, 100 m margin) and step 3 (pixel size starts equal to the cell and cannot exceed it).
- Fix: the Processing help showed "_Grade Padrão_ x .shp" because the file name used angle brackets (regression test).
- New rule and test: the Help texts are reviewed for every version (i18n.HELP_REVIEWED_VERSION must match the plugin version).

## 1.5.0 (2026)
- Step 1: choose the vector grid: create a new one with the cell size chosen by the user (independent of the interpolation pixel), or use an existing grid (only the cells touching the field are used).
- The created grid is saved in the output folder as "<boundary layer>_Grade Padrão_<cell>x<cell>.shp", with whole cells, and can be reused; when it already exists the wizard asks whether to reuse or overwrite it.
- Outputs in Shapefile; mean columns named after the attributes (up to 10 characters).
- Interpolated rasters cover the boundary rectangle plus a 100 m margin and are never masked or clipped.
- Fix: the zonal mean is computed on whole cells and the grid is clipped by the boundary only afterwards, so border cells are never left without value (regression test).
- Step 3: the pixel starts equal to the cell size and cannot exceed it.
- Processing algorithm: new "Grid cell size" and optional "Existing grid" parameters.

## 1.4.0 (2026)
- Step 3 has a single layout (the standard layout was removed); sliders now cover P from 0.5 to 5.0 and the radius from 1x to 6x the coverage distance.
- Weight chart corrected after Shepard (1968): the IDW weight 1/d^P is shown relative to the weight at the typical pixel-to-sample distance (equal to 1 there), grows without limit near the sample (axis cut at 4) and has distance ticks. The artificial plateau at distance 0 and the grey reference curves were removed (regression test).
- New bars "Influence on a typical pixel": share of each neighbouring sample, lambda = w_i / sum w_j (100 % in total), with the real samples of the attribute.
- Cross-validation table and fine search cover P from 0.5 to 5.0 and radius up to 6x (regression test).
- "Learn more" about how IDW computes the weights, with reference.

## 1.3.2 (2026)
- Step 1: the output folder comes filled in: the last folder used or, the first time, the "AgriPrecisa" subfolder inside the QGIS project folder, created automatically. If the project is not saved and there is no previous folder, a hint asks to save the project or choose a folder.

## 1.3.1 (2026)
- New names: "Ajuste automático" / "Ajuste automático para todos" (EN: Auto-fit / Auto-fit all).
- Modes renamed to "Layout Didático" (visual, for classes) and "Layout Padrão" (free values), with tooltips.
- Parameter table origin "automático" for values from the auto-fit.

## 1.3.0 (2026)
- IDW parameters per attribute (each attribute has its own spatial dependence and variability):
  - attribute selector at the top of step 3; sliders, curve and preview apply to the chosen attribute;
  - summary table with P, radius and origin (default, validation, manual) of every attribute;
  - "Suggest for this one" (with the RMSE table) and "Suggest for all".
- Each attribute starts with P = 2 and a radius of twice its own coverage distance.
- Cross-validation never suggests a radius that leaves more than 1% of the field without value (shown in grey in the table). Regression test added.
- Processing algorithm: new option to choose P and radius of each attribute by cross-validation.
- Step 3 inside a scroll area (no overlapping texts on small screens); larger default window.
- Fix: radius of exactly 1.5x was described as "short" because of rounding (regression test).

## 1.2.0 (2026)
- Step 3: "Show samples" toggle in the map preview (hidden by default above 500 samples).
- Search radius based on the coverage distance (95th percentile of the distance from field pixels to the nearest sample). Fixes strips without value between sensor passes, where the density-based spacing was too small.
- "Suggest P and radius" button: cross-validation with up to 60 validation samples spread over the field, away from the border, without outliers (beyond 3 SD) and balanced across low, medium and high values; exclusion zone around each validated sample; RMSE table by P and radius with "Apply".

## 1.1.0 (2026)
- Wizard step 3, student mode (default, remembered between runs):
  - power P slider from 1.0 to 3.0 (step 0.1) with simple explanation and "Learn more";
  - search radius slider in multiples (1x to 4x) of the mean sample spacing, estimated from the sampling density;
  - weight x distance curve with P = 1 and P = 3 references and the radius marker;
  - live low-resolution map preview with the real samples, attribute selector and colour bar.
- Advanced mode keeps the free numeric fields (P above 3, unlimited radius).
- Fix (found during development): preview mask was empty because a temporary point geometry was freed before GEOS used it (regression test added).

## 1.0.3 (2026)
- Wizard step 2: sample counts and density are left-aligned and shown only on layer rows.

## 1.0.2 (2026)
- Wizard step 2: field area in hectares in the header; samples inside the field and sampling density (samples/ha) for each layer and attribute; tooltip with the samples used including the tolerance.
- Summary step shows the field area.

## 1.0.1 (2026)
- Wizard: "[EPSG:xxxx]" shown after each layer name; warning icon with tooltip for layers not in a projected CRS in metres (steps 1 and 2).
- Fix: messages showed an empty CRS name when the project had no CRS.

## 1.0.0 (2026)
- First public release.
- IDW vector grid tool: step-by-step wizard and Processing algorithm.
- Interface in Portuguese, English and Spanish.
