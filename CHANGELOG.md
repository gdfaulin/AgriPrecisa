# Changelog

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
