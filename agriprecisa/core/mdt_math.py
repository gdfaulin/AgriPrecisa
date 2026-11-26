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

import math

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
DEFAULT_PLANT_HEIGHT = 0.30   # m, plant mask: pixels at least this high above the DTM
MAX_AUTO_SLOPE = 1.0          # 100 percent, cap of the automatic slope
DEFAULT_RESOLUTION = 0.25
DEFAULT_TOLERANCE = 0.25
METHOD_OPENING = 0            # morphological opening (default)
METHOD_SLOPE = 1              # slope-based filter (Vosselman, 2000)
DEFAULT_VOSSELMAN_SLOPE = 30.0   # percent, as in SAGA and QGIS DTM filter (slope-based)
MAX_FULL_KERNEL = 6           # radius (pixels) up to which every neighbour is tested
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


CROP_FIELDS = ("SPACING", "RESOLUTION", "TOLERANCE")


def crop_field_values(index):
    """Values the dialog shows in the fields for a crop; {} for Custom (current values kept)."""
    try:
        index = int(index)
    except (TypeError, ValueError):
        return {}
    if not 0 <= index < len(CROPS) or index == CUSTOM:
        return {}
    _key, spacing, res, tol = CROPS[index]
    return {"SPACING": spacing, "RESOLUTION": res, "TOLERANCE": tol}


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


def terrain_slope(opening, valid, pixel, window):
    """
    Local terrain slope (m/m) from the opening surface smoothed over the window (the opening
    follows the soil under the plants).
    """
    from scipy import ndimage
    base = np.where(valid & np.isfinite(opening), opening, np.nan)
    filled = fill_nearest(base)
    if np.isnan(filled).all():
        return np.zeros(opening.shape)
    smooth = ndimage.uniform_filter(filled, size=window)
    gy, gx = np.gradient(smooth, pixel)
    return np.clip(np.hypot(gx, gy), 0.0, MAX_AUTO_SLOPE)


def soil_threshold(opening, valid, pixel, window, tolerance, slope_percent=0.0):
    """
    Height above the opening up to which a pixel is soil: tolerance plus slope x half window.
    On a slope the opening lies below the soil towards the edges of the window by up to
    slope x (window / 2) (progressive morphological filter, Zhang et al., 2003).
    ``slope_percent`` > 0 uses that slope everywhere; 0 estimates it pixel by pixel; None
    ignores the slope. Returns (threshold, slope used in percent: median over valid pixels).
    """
    half = window * pixel / 2.0
    if slope_percent is None:
        return tolerance, 0.0
    if slope_percent > 0:
        s = slope_percent / 100.0
        return tolerance + s * half, float(slope_percent)
    from scipy import ndimage
    slope = terrain_slope(opening, valid, pixel, window)
    used = float(np.median(slope[valid])) * 100 if valid.any() else 0.0
    # steepest slope within the window: at a crest or terrace edge the gradient cancels out
    # right at the break, but the opening is cut there by the slopes around it
    return tolerance + ndimage.maximum_filter(slope, size=window) * half, used


def classify_soil(dsm, opening, valid, tolerance):
    """Boolean mask of soil pixels: at most ``tolerance`` (number or array) above the opening."""
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


def _kernel_offsets(radius):
    """
    Neighbour offsets (dy, dx) tested by the slope-based filter. Small radii use the whole
    disc; larger radii use 16 directions at about 14 distances (a few hundred shifts instead
    of thousands), enough to find the soil around a plant and much faster.
    """
    r = int(radius)
    if r <= MAX_FULL_KERNEL:
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        keep = (np.hypot(yy, xx) <= r + 1e-9) & ((yy != 0) | (xx != 0))
        return list(zip(yy[keep].tolist(), xx[keep].tolist()))
    dists = np.unique(np.concatenate([np.arange(1, 5), np.round(np.geomspace(4, r, 10))])).astype(int)
    offs = set()
    for ang in np.radians(np.arange(0.0, 360.0, 22.5)):
        for d in dists:
            offs.add((int(round(d * math.sin(ang))), int(round(d * math.cos(ang)))))
    offs.discard((0, 0))
    return sorted(offs)


def slope_based_ground(dsm, valid, pixel, radius_px, slope_percent, tolerance=0.0):
    """
    Slope-based filter (Vosselman, 2000; as SAGA and QGIS DTM filter (slope-based)): a pixel is
    ground when no neighbour within the radius is lower by more than
    dz_max(d) = d x slope + tolerance, d being the distance between them. The tolerance plays
    the role of the confidence interval that relaxes the filter.
    """
    r = max(1, int(radius_px))
    s = slope_percent / 100.0
    h, w = dsm.shape
    pad = np.pad(np.where(valid, dsm, np.inf), r, mode="constant", constant_values=np.inf)
    low = np.full(dsm.shape, np.inf)
    for dy, dx in _kernel_offsets(r):
        dz = math.hypot(dy, dx) * pixel * s + tolerance
        np.minimum(low, pad[r + dy:r + dy + h, r + dx:r + dx + w] + dz, out=low)
    with np.errstate(invalid="ignore"):
        return valid & (dsm <= low)


def remove_furrows(dtm, valid, pixel, spacing, fraction):
    """
    Furrow removal: Gaussian smoothing of the DTM with sigma = fraction x row spacing. The
    micro-relief of furrows and ridges (period = row spacing) is removed and the DTM follows
    the mean soil level (sigma of half a spacing keeps less than 1 percent of that relief).
    ``fraction`` 0 leaves the DTM unchanged.
    """
    if not fraction or fraction <= 0:
        return dtm
    from scipy import ndimage
    sigma = fraction * spacing / pixel
    ok = np.isfinite(dtm)
    num = ndimage.gaussian_filter(np.where(ok, dtm, 0.0), sigma, mode="nearest")
    den = ndimage.gaussian_filter(ok.astype("float64"), sigma, mode="nearest")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = np.where(den > 1e-6, num / np.where(den > 1e-6, den, 1.0), np.nan)
    out[~valid] = np.nan
    return out


def classify_ground(dsm, valid, pixel, window, tolerance, slope_percent, method, opening=None):
    """
    Soil (ground) pixels with either method. Returns (soil, slope used in percent, opening).
    Opening: slope 0 = automatic (see soil_threshold). Slope-based: slope 0 = 30 percent;
    radius = half the window.
    """
    if method == METHOD_SLOPE:
        s = slope_percent if slope_percent and slope_percent > 0 else DEFAULT_VOSSELMAN_SLOPE
        return slope_based_ground(dsm, valid, pixel, window // 2, s, tolerance), float(s), None
    if opening is None:
        opening = ground_surface(dsm, valid, window)
    thr, used = soil_threshold(opening, valid, pixel, window, tolerance, slope_percent)
    return classify_soil(dsm, opening, valid, thr), used, opening


def dtm_from_dsm(dsm, window, tolerance, fill=fill_nearest, pixel=1.0, slope_percent=None,
                 method=METHOD_OPENING, spacing=None, furrows=0.0):
    """Whole method on an array (NaN = no data). Returns (dtm, height, soil)."""
    valid = np.isfinite(dsm)
    if method == METHOD_OPENING and slope_percent is None:
        opening = ground_surface(dsm, valid, window)
        soil = classify_soil(dsm, opening, valid, tolerance)
    else:
        soil, _used, _op = classify_ground(dsm, valid, pixel, window, tolerance, slope_percent or 0, method)
    filled = fill(np.where(soil, dsm, np.nan))
    dtm = smooth_dtm(filled, dsm, valid, window)
    dtm, height = apply_furrows(dtm, dsm, valid, pixel, spacing, furrows)
    return dtm, height, soil


def apply_furrows(dtm, dsm, valid, pixel, spacing, furrows):
    """
    Furrow removal and plant height. With furrow removal the DTM stays at the mean soil level
    (it is not cut back to the DSM, which would bring it down into every furrow again); the
    soil at the bottom of the furrows lies below that level and gets height 0.
    Returns (dtm, height).
    """
    if furrows and spacing:
        dtm = remove_furrows(dtm, valid, pixel, spacing, furrows)
        with np.errstate(invalid="ignore"):
            return dtm, np.maximum(dsm - dtm, 0.0)
    return dtm, dsm - dtm


# ---------------------------------------------------------------------------
# Plant mask and its patches
# ---------------------------------------------------------------------------
def plant_mask(height, valid, min_height):
    """1 where the plant height is at least ``min_height`` (plant), else 0 (soil)."""
    with np.errstate(invalid="ignore"):
        return valid & np.isfinite(height) & (height >= min_height)


def plant_patches(mask, height, pixel):
    """
    Connected patches of the plant mask (4-neighbourhood, like GDAL Polygonize).
    Returns (labels int32 raster, list of dicts id, area, mean, max).
    """
    from scipy import ndimage
    labels, n = ndimage.label(mask)
    labels = labels.astype(np.int32)
    if n == 0:
        return labels, []
    ids = np.arange(1, n + 1)
    h = np.where(np.isfinite(height), height, 0.0)
    count = ndimage.sum(np.ones(mask.shape), labels, ids)
    mean = ndimage.mean(h, labels, ids)
    hmax = ndimage.maximum(h, labels, ids)
    return labels, [{"id": int(i), "area": float(c) * pixel * pixel, "mean": float(m), "max": float(x)}
                    for i, c, m, x in zip(ids, count, mean, hmax)]


# ---------------------------------------------------------------------------
# Row spacing detection (for the measuring step of the wizard)
# ---------------------------------------------------------------------------
def _profile(u, values, step):
    """Mean of ``values`` in bins of ``step`` along u (NaN where a bin has few pixels)."""
    b = np.floor((u - u.min()) / step).astype(np.int64)
    total = np.bincount(b)
    sums = np.bincount(b, weights=values, minlength=total.size)
    ok = total >= max(3, 0.2 * np.median(total[total > 0]))
    return np.where(ok, sums / np.maximum(total, 1), np.nan)


def detect_spacing(dsm, valid, gt, min_spacing=0.3, max_spacing=10.0, max_samples=200000):
    """
    Row spacing and direction found in a DSM window. The DSM minus a broad moving average
    (relief removed) is projected across the rows for every direction; the direction whose
    profile oscillates the most, and the period of that oscillation, give the rows.
    Coordinates are local to the window: x = (col + 0.5) * pixel, y = -(row + 0.5) * pixel,
    u = x cos(theta) + y sin(theta). Returns (spacing m, theta radians across the rows,
    score 0..1, phi) where the row centres are at u = phi + k * spacing; (None, None, 0, None)
    when nothing is found.
    """
    from scipy import ndimage
    pixel = abs(gt[1])
    if valid.sum() < 100:
        return None, None, 0.0, None
    filled = fill_nearest(np.where(valid, dsm, np.nan))
    size = max(3, int(round(2.5 * max_spacing / pixel)) | 1)
    detail = filled - ndimage.uniform_filter(filled, size=min(size, min(dsm.shape)))
    rows, cols = np.nonzero(valid)
    if rows.size > max_samples:
        sel = np.random.default_rng(0).choice(rows.size, max_samples, replace=False)
        rows, cols = rows[sel], cols[sel]
    x = (cols + 0.5) * pixel
    y = -(rows + 0.5) * pixel
    vals = detail[rows, cols]
    step = pixel

    def best_period(theta):
        u = x * math.cos(theta) + y * math.sin(theta)
        prof = _profile(u, vals, step)
        prof = np.where(np.isfinite(prof), prof - np.nanmean(prof), 0.0)
        if prof.size < 8:
            return 0.0, None
        spec = np.abs(np.fft.rfft(prof * np.hanning(prof.size))) ** 2
        freqs = np.fft.rfftfreq(prof.size, step)
        ok = (freqs >= 1.0 / max_spacing) & (freqs <= 1.0 / min_spacing)
        if not ok.any():
            return 0.0, None
        i = np.flatnonzero(ok)[np.argmax(spec[ok])]
        power = spec[i] / max(spec[1:].sum(), 1e-12)
        return float(power), 1.0 / freqs[i]

    angles = np.radians(np.arange(0.0, 180.0, 2.0))
    scores = [best_period(t) for t in angles]
    k = int(np.argmax([sc for sc, _ in scores]))
    fine = angles[k] + np.radians(np.arange(-2.0, 2.01, 0.25))
    fscores = [best_period(t) for t in fine]
    j = int(np.argmax([sc for sc, _ in fscores]))
    score, period = fscores[j]
    if period is None:
        return None, None, 0.0, None
    theta = float(fine[j]) % math.pi
    # refine direction and period together with the comb amplitude (sharper than the FFT peak)
    def comb(theta_, s_):
        u = x * math.cos(theta_) + y * math.sin(theta_)
        prof = _profile(u, vals, step)
        finite = np.isfinite(prof)
        pos = np.flatnonzero(finite) * step
        p = prof[finite] - prof[finite].mean()
        w = 2 * math.pi / s_
        return math.hypot(np.sum(p * np.cos(w * pos)), np.sum(p * np.sin(w * pos))) / max(p.size, 1)

    spacing = period
    for span_deg, n_t, span_s in ((3.0, 31, 0.1), (0.5, 21, 0.03)):
        cands = [(comb(t, spacing), t) for t in theta + np.radians(np.linspace(-span_deg, span_deg, n_t))]
        theta = max(cands)[1]
        cands = [(comb(theta, s_), s_) for s_ in np.linspace((1 - span_s) * spacing, (1 + span_s) * spacing, 41)]
        spacing = float(max(cands)[1])
    # phase of the comb: the profile peaks (plants above the local relief) are the row centres
    u = x * math.cos(theta) + y * math.sin(theta)
    prof = _profile(u, vals, step)
    finite = np.isfinite(prof)
    pos = np.flatnonzero(finite) * step
    p = prof[finite] - prof[finite].mean()
    w = 2 * math.pi / spacing
    phase = math.atan2(np.sum(p * np.sin(w * pos)), np.sum(p * np.cos(w * pos)))
    phi = float(u.min() + (phase / w) % spacing)
    return spacing, float(theta) % math.pi, float(score), phi
