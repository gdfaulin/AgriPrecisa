# -*- coding: utf-8 -*-
"""
AgriPrecisa: terrain model (DTM) and plant height from a drone surface model (DSM)
in row crops. Pure numpy/scipy, no QGIS imports (unit-tested with pytest).

Method (progressive morphological approach, simplified for row crops):

1. a window a little wider than the inter-row always contains some visible soil;
2. morphological opening (minimum then maximum filter) with that window builds a
   surface that passes under the plants;
3. pixels close to that surface (within a tolerance) are classified as soil;
4. the terrain under the plants is interpolated from the soil pixels (done with GDAL
   FillNodata in the algorithm, or with ``fill_nearest`` here);
5. a moving average over the window smooths the result, which is never above the DSM.
"""

import numpy as np

# Typical values per crop: inter-row spacing (m), working resolution (m), soil tolerance (m).
# Resolution keeps at least PIXELS_PER_ROW pixels per inter-row; tolerance stays well below
# the height of the plants.
CROPS = [
    ("coffee", 3.6, 0.25, 0.25),
    ("citrus", 6.5, 0.25, 0.30),
    ("maize", 0.8, 0.10, 0.15),
    ("soybean", 0.5, 0.10, 0.10),
    ("sugarcane", 1.5, 0.15, 0.20),
    ("grapevine", 2.5, 0.20, 0.20),
    ("eucalyptus", 3.0, 0.25, 0.30),
    ("custom", None, None, None),
]
CUSTOM = len(CROPS) - 1

DEFAULT_FACTOR = 1.5
DEFAULT_RESOLUTION = 0.25
DEFAULT_TOLERANCE = 0.25
PIXELS_PER_ROW = 4     # recommended: at least 4 pixels across the inter-row
MIN_WINDOW = 5         # below this the window cannot "see" the inter-row
LOW_SOIL_PERCENT = 10
HIGH_SOIL_PERCENT = 85


def resolve_parameters(crop_index, spacing, resolution, tolerance):
    """
    Values actually used. Zero (or None) in a field means "use the value of the crop".
    Returns (spacing, resolution, tolerance); spacing is None when it is still unknown
    (custom crop without spacing).
    """
    _key, c_spacing, c_res, c_tol = CROPS[crop_index]
    spacing = spacing if spacing and spacing > 0 else c_spacing
    if not (resolution and resolution > 0):
        resolution = c_res
        if resolution is None:
            resolution = DEFAULT_RESOLUTION
            if spacing:
                resolution = min(DEFAULT_RESOLUTION, round(spacing / PIXELS_PER_ROW, 2))
    if not (tolerance and tolerance > 0):
        tolerance = c_tol if c_tol is not None else DEFAULT_TOLERANCE
    return spacing, resolution, tolerance


def recommended_resolution(spacing):
    """Coarsest resolution that keeps PIXELS_PER_ROW pixels across the inter-row."""
    return spacing / PIXELS_PER_ROW


def window_pixels(spacing, factor, pixel):
    """Odd window size in pixels (spacing x factor / pixel); may be below MIN_WINDOW."""
    n = int(round(spacing * factor / pixel))
    if n % 2 == 0:
        n += 1
    return n


def ground_surface(dsm, valid, window):
    """Morphological opening of the DSM: a surface that passes under the plants."""
    from scipy import ndimage
    eroded = ndimage.minimum_filter(np.where(valid, dsm, np.inf), size=window)
    return ndimage.maximum_filter(np.where(np.isfinite(eroded), eroded, -np.inf), size=window)


def classify_soil(dsm, opening, valid, tolerance):
    """Boolean mask of soil pixels: at most ``tolerance`` above the opening surface."""
    with np.errstate(invalid="ignore"):
        return valid & np.isfinite(opening) & ((dsm - opening) <= tolerance)


def soil_percent(soil, valid):
    n = int(valid.sum())
    return 100.0 * int(soil.sum()) / n if n else 0.0


def fill_nearest(values):
    """Fills NaN with the nearest valid value (simple stand-in for GDAL FillNodata)."""
    from scipy import ndimage
    missing = np.isnan(values)
    if not missing.any() or missing.all():
        return values.copy()
    idx = ndimage.distance_transform_edt(missing, return_distances=False, return_indices=True)
    return values[tuple(idx)]


def smooth_dtm(filled, dsm, valid, window):
    """Moving average (ignoring NaN) over the window; never above the DSM; NaN outside data."""
    from scipy import ndimage
    values = np.where(np.isnan(filled), 0.0, filled)
    weights = (~np.isnan(filled)).astype("float64")
    total = ndimage.uniform_filter(values, size=window)
    count = ndimage.uniform_filter(weights, size=window)
    with np.errstate(invalid="ignore", divide="ignore"):
        dtm = np.where(count > 1e-9, total / np.where(count > 1e-9, count, 1.0), np.nan)
        dtm = np.minimum(dtm, dsm)
    dtm[~valid] = np.nan
    return dtm


def height_stats(height, soil, valid):
    """Mean, 95th percentile and maximum of the plant height (plant pixels only)."""
    plants = valid & ~soil & np.isfinite(height)
    if not plants.any():
        return None
    h = height[plants]
    return {"mean": float(np.mean(h)), "p95": float(np.percentile(h, 95)),
            "max": float(np.max(h)), "plant_percent": 100.0 * h.size / max(int(valid.sum()), 1)}


def dtm_from_dsm(dsm, window, tolerance, fill=fill_nearest):
    """Whole method on an array (NaN = no data). Returns (dtm, height, soil)."""
    valid = np.isfinite(dsm)
    opening = ground_surface(dsm, valid, window)
    soil = classify_soil(dsm, opening, valid, tolerance)
    filled = fill(np.where(soil, dsm, np.nan))
    dtm = smooth_dtm(filled, dsm, valid, window)
    return dtm, dsm - dtm, soil
