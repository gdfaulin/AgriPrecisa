# Changelog

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
