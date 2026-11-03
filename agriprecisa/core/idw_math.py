# -*- coding: utf-8 -*-
"""
AgriPrecisa: pure numerical functions (no QGIS imports).

Kept free of QGIS so they can be unit-tested with plain pytest.
"""

import math
import re
import unicodedata

import numpy as np

NODATA = -9999.0


def safe_name(text, limit=40):
    """Strip accents and special characters to build file/field names."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    text = re.sub(r"[^0-9A-Za-z_]+", "_", text).strip("_")
    return (text or "field")[:limit]


def snap_extent(xmin, ymin, xmax, ymax, res):
    """
    Snap a bounding box outward to multiples of the pixel size.

    Returns (xmin, ymin, xmax, ymax, ncol, nrow), always at least 1 x 1.
    """
    if res <= 0:
        raise ValueError("Pixel size must be positive")
    sx = math.floor(xmin / res) * res
    sy = math.floor(ymin / res) * res
    ex = math.ceil(xmax / res) * res
    ey = math.ceil(ymax / res) * res
    ncol = max(1, int(round((ex - sx) / res)))
    nrow = max(1, int(round((ey - sy) / res)))
    return sx, sy, sx + ncol * res, sy + nrow * res, ncol, nrow


def unique_prefixes(pairs):
    """
    Build unique, safe column prefixes for (layer_name, field_name) pairs.

    When the same field name appears in more than one layer, the layer name
    is prepended. Remaining collisions get a numeric suffix.
    """
    names = [f for _, f in pairs]
    used, out = set(), []
    for layer_name, field in pairs:
        base = safe_name(field)
        if names.count(field) > 1:
            base = safe_name(layer_name, 20) + "_" + base
        prefix, k = base, 2
        while prefix in used:
            prefix, k = f"{base}_{k}", k + 1
        used.add(prefix)
        out.append(prefix)
    return out


MIN_NEIGHBOURS = 4            # every pixel uses at least this many samples
DEFAULT_MAX_NEIGHBOURS = 16   # and at most this many (nearest first)
FALLBACK_NEIGHBOURS = MIN_NEIGHBOURS   # kept for older imports


def _neighbour_mask(d2, r2, min_n, max_n):
    """
    Boolean mask (rows = pixels, columns = samples) of the samples each pixel uses:
      * the samples within the search radius (all samples when ``r2`` is None);
      * if the radius reaches fewer than ``min_n`` samples, the ``min_n`` nearest
        (the minimum is always met, even beyond the radius);
      * if it reaches more than ``max_n``, only the ``max_n`` nearest (the maximum
        limits the radius). ``max_n`` = 0 means no maximum.
    Also returns the rows where the minimum had to go beyond the radius.
    """
    n = d2.shape[1]
    valid = (d2 <= r2) if r2 is not None else np.ones_like(d2, dtype=bool)
    if max_n and max_n < n:
        k = int(max_n)
        nearest = np.argpartition(d2, k - 1, axis=1)[:, :k]
        keep = np.zeros_like(valid)
        np.put_along_axis(keep, nearest, True, axis=1)
        valid &= keep
    counts = valid.sum(axis=1)
    k_min = min(int(min_n or 0), n)
    short = counts < k_min
    if k_min > 0 and short.any():
        rows = np.flatnonzero(short)
        nearest = np.argpartition(d2[rows], k_min - 1, axis=1)[:, :k_min]
        valid[rows] = False
        valid[rows[:, None], nearest] = True
    return valid, short


def idw_grid(xs, ys, zs, xmin, ymax, ncol, nrow, res, power, radius, callback=None,
             min_neighbours=MIN_NEIGHBOURS, max_neighbours=0, return_fallback=False,
             fallback_neighbours=None):
    """
    Inverse Distance Weighting evaluated at each pixel centre.

    value = sum(z / d^P) / sum(1 / d^P) over the pixel's neighbours, chosen as in Surfer,
    ArcGIS and SAGA: the samples within ``radius`` (0 = no radius), but never fewer than
    ``min_neighbours`` (the nearest ones are taken even beyond the radius, so the map
    never has holes) and never more than ``max_neighbours`` (the nearest ones; 0 = no
    maximum). The radius only saves computation in very dense sampling.

    A pixel lying exactly on a sample takes that sample's value (mean if several samples
    coincide). ``callback(fraction)`` may return False to cancel; the function then
    returns None. With ``return_fallback`` the result is (grid, mask of pixels whose
    minimum had to go beyond the radius). Work is done in blocks to bound memory use.
    ``fallback_neighbours`` is the old name of ``min_neighbours``.
    """
    if fallback_neighbours is not None:
        min_neighbours = fallback_neighbours
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    zs = np.asarray(zs, dtype=np.float64)

    cx = xmin + (np.arange(ncol) + 0.5) * res
    cy = ymax - (np.arange(nrow) + 0.5) * res
    gx, gy = np.meshgrid(cx, cy)
    gx, gy = gx.ravel(), gy.ravel()

    out = np.full(gx.size, NODATA, dtype=np.float64)
    used_fallback = np.zeros(gx.size, dtype=bool)
    n = xs.size
    if n == 0:
        grid = out.reshape(nrow, ncol)
        return (grid, used_fallback.reshape(nrow, ncol)) if return_fallback else grid

    block = max(1, int(4_000_000 // n))
    r2 = radius * radius if radius > 0 else None
    if max_neighbours and min_neighbours and max_neighbours < min_neighbours:
        max_neighbours = min_neighbours

    for start in range(0, gx.size, block):
        end = min(start + block, gx.size)
        dx = gx[start:end, None] - xs[None, :]
        dy = gy[start:end, None] - ys[None, :]
        d2 = dx * dx + dy * dy

        valid, short = _neighbour_mask(d2, r2, min_neighbours, max_neighbours)
        if r2 is not None:
            used_fallback[start:end] = short
        zero = d2 < 1e-12
        d2_safe = np.where(zero, 1.0, d2)
        weights = np.where(valid, d2_safe ** (-power / 2.0), 0.0)

        on_sample = zero.any(axis=1)
        if on_sample.any():
            weights[on_sample] = zero[on_sample].astype(float)

        wsum = weights.sum(axis=1)
        ok = wsum > 0
        values = np.full(end - start, NODATA)
        values[ok] = (weights[ok] @ zs) / wsum[ok]
        out[start:end] = values

        if callback is not None and callback(end / gx.size) is False:
            return None
    grid = out.reshape(nrow, ncol)
    return (grid, used_fallback.reshape(nrow, ncol)) if return_fallback else grid


def select_neighbour_distances(d_sorted, radius, min_n=MIN_NEIGHBOURS, max_n=0):
    """Same rule as idw_grid for one pixel, given its sorted distances to every sample."""
    d = np.asarray(d_sorted, float)
    inside = d[d <= radius] if radius and radius > 0 else d
    if inside.size < min_n:
        inside = d[:min_n]
    if max_n:
        inside = inside[:max(max_n, min_n)]
    return inside


def nearest_k_distances(px, py, xs, ys, k):
    """
    Sorted distances (rows = points (px, py), columns = 1st..k-th nearest sample), in
    blocks. Columns beyond the number of samples are +inf.
    """
    px, py = np.asarray(px, float), np.asarray(py, float)
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    k = max(int(k), 1)
    out = np.full((px.size, k), np.inf)
    if xs.size == 0:
        return out
    kk = min(k, xs.size)
    block = max(1, int(4_000_000 // xs.size))
    for s in range(0, px.size, block):
        e = min(s + block, px.size)
        d2 = (px[s:e, None] - xs[None, :]) ** 2 + (py[s:e, None] - ys[None, :]) ** 2
        part = np.partition(d2, kk - 1, axis=1)[:, :kk] if kk < xs.size else d2
        out[s:e, :kk] = np.sqrt(np.sort(part, axis=1))
    return out


def kth_nearest_distances(px, py, xs, ys, k):
    """Distance from each point (px, py) to its k-th nearest sample."""
    if k < 1:
        return np.full(np.asarray(px).size, np.inf)
    return nearest_k_distances(px, py, xs, ys, k)[:, int(k) - 1]


def share_beyond_radius(knn, k, radius):
    """
    % of the points whose k-th nearest sample is farther than ``radius``, from the
    nearest_k_distances matrix: where the radius reaches fewer than ``k`` samples.
    """
    knn = np.asarray(knn, float)
    if knn.size == 0 or not radius or radius <= 0 or k < 1:
        return 0.0
    col = knn[:, min(int(k), knn.shape[1]) - 1]
    return float(np.mean(col > radius) * 100.0)


def radius_for_neighbours(px, py, xs, ys, k, q=95.0):
    """
    Search radius that does not cut the ``k`` nearest neighbours in ``q`` % of the
    points (px, py): the q-th percentile of the distance to the k-th nearest sample,
    rounded up to whole metres. With the radius at this value the maximum of neighbours,
    not the radius, decides how many samples a pixel uses.
    """
    d = kth_nearest_distances(px, py, xs, ys, k)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return None
    return float(math.ceil(np.percentile(d, q)))


def radius_from_knn(knn, max_n, min_n=MIN_NEIGHBOURS, coverage=None, q=95.0):
    """
    Search radius that does not get in the way of the neighbour rule, from the
    nearest_k_distances matrix of the field pixels: it reaches ``max_n`` samples in ``q`` %
    of the field and ``min_n`` samples in all of it (never below ``coverage``), rounded up
    to whole metres. Used as the default radius and after the auto-fit.
    """
    knn = np.asarray(knn, float)
    if knn.size == 0:
        return None
    cols = knn.shape[1]
    kmax = knn[:, min(max(int(max_n), 1), cols) - 1]
    kmin = knn[:, min(max(int(min_n), 1), cols) - 1]
    kmax, kmin = kmax[np.isfinite(kmax)], kmin[np.isfinite(kmin)]
    parts = [float(coverage or 0.0)]
    if kmax.size:
        parts.append(float(np.percentile(kmax, q)))
    if kmin.size:
        parts.append(float(kmin.max()))
    return float(math.ceil(max(parts)))


def sample_density(n_samples, area_ha):
    """Samples per hectare; None when the area is not positive."""
    if area_ha is None or area_ha <= 0:
        return None
    return n_samples / area_ha


# ---------------------------------------------------------------------------
# Helpers for the didactic (student mode) parameter page
# ---------------------------------------------------------------------------
STUDENT_POWER_MIN, STUDENT_POWER_MAX = 0.5, 5.0
STUDENT_RADIUS_MIN, STUDENT_RADIUS_MAX = 1.0, 10.0  # multiples of the coverage distance
DEFAULT_RADIUS_MULTIPLE = 2.0


def mean_spacing(density):
    """
    Mean distance between samples (m) for a regular grid with ``density`` samples/ha:
    sqrt(10 000 m2 / density). None when the density is unknown or not positive.
    """
    if density is None or density <= 0:
        return None
    return math.sqrt(10000.0 / density)


def power_band(power):
    """'low' (< 1.5), 'mid' (1.5 to 2.5) or 'high' (> 2.5)."""
    if power < 1.5:
        return "low"
    if power <= 2.5:
        return "mid"
    return "high"


def radius_band(multiple):
    """'short' (< 1.5x spacing), 'ok' (1.5x to 2.5x) or 'long' (> 2.5x)."""
    if multiple < 1.5:
        return "short"
    if multiple <= 2.5:
        return "ok"
    return "long"


def relative_weights(distances, power, d_ref):
    """
    IDW weight 1/d^P relative to the weight at the reference distance ``d_ref``:
    (d_ref / d)^P. It equals 1 at d_ref, grows without limit as d -> 0 (a pixel lying on a
    sample takes its value: IDW is an exact interpolator, Shepard 1968) and decays beyond.
    Returns inf where d == 0.
    """
    d = np.asarray(distances, dtype=float)
    with np.errstate(divide="ignore"):
        return np.where(d > 0, (d_ref / np.where(d > 0, d, 1.0)) ** power, np.inf)


def normalized_weights(distances, power):
    """
    Share of each sample in the estimate of one pixel: lambda_i = d_i^-P / sum(d_j^-P),
    summing to 1 (Shepard, 1968). A sample at distance 0 takes 100 %.
    """
    d = np.asarray(distances, dtype=float)
    if d.size == 0:
        return d
    zero = d <= 0
    if zero.any():
        return zero / zero.sum()
    w = d ** (-power)
    return w / w.sum()


def typical_pixel_neighbours(px, py, xs, ys, radius, max_neighbours=None,
                             min_neighbours=None):
    """
    Distances (ascending) from a typical field pixel to the samples it uses: those within
    ``radius`` (0 = all), at least ``min_neighbours`` and at most ``max_neighbours``.
    The typical pixel is the one whose nearest-sample distance is closest to the median of
    all pixels, so the bars show what happens in an ordinary place of the field.
    """
    px, py = np.asarray(px, float), np.asarray(py, float)
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    if px.size == 0 or xs.size == 0:
        return np.array([])
    nearest = nearest_distances(px, py, xs, ys)
    k = int(np.argmin(np.abs(nearest - np.median(nearest))))
    d = np.sort(np.hypot(xs - px[k], ys - py[k]))
    return select_neighbour_distances(d, radius, min_neighbours or 0, max_neighbours or 0)


# ---------------------------------------------------------------------------
# Coverage distance and cross-validation (automatic choice of P and radius)
# ---------------------------------------------------------------------------
def nearest_distances(px, py, xs, ys):
    """Distance from each point (px, py) to the nearest sample (xs, ys), in blocks."""
    px, py = np.asarray(px, float), np.asarray(py, float)
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    out = np.full(px.size, np.inf)
    if xs.size == 0:
        return out
    block = max(1, int(4_000_000 // xs.size))
    for s in range(0, px.size, block):
        e = min(s + block, px.size)
        d2 = (px[s:e, None] - xs[None, :]) ** 2 + (py[s:e, None] - ys[None, :]) ** 2
        out[s:e] = np.sqrt(d2.min(axis=1))
    return out


def coverage_distances(px, py, xs, ys, return_nearest=False):
    """
    (typical, coverage) distances from field pixels to the nearest sample:
    typical  = median  -> how far a usual pixel is from data (used as exclusion zone)
    coverage = 95th percentile -> 95 % of the field is within this distance of a sample
    Works for regular grids and for sensor passes (dense along the line, sparse between lines).
    """
    d = nearest_distances(px, py, xs, ys)
    d = d[np.isfinite(d)]
    if d.size == 0:
        return (None, None, d) if return_nearest else (None, None)
    typical, cover = float(np.percentile(d, 50)), float(np.percentile(d, 95))
    return (typical, cover, d) if return_nearest else (typical, cover)


def select_validation_samples(xs, ys, zs, edge_dist, n_target=60, edge_buffer=0.0,
                              sd_limit=3.0, n_strata=3, seed=42):
    """
    Indices of validation samples for cross-validation:
      * only samples inside the field and at least ``edge_buffer`` m from its border
        (``edge_dist`` < 0 marks samples outside the field);
      * outliers removed: values beyond ``sd_limit`` standard deviations from the mean;
      * spread over the whole field (spatial blocks) and balanced across ``n_strata``
        value classes (low, medium, high), so extremes of the real variability are kept.
    Fixed ``seed``: the same data always give the same selection.
    """
    xs, ys, zs = (np.asarray(a, float) for a in (xs, ys, zs))
    edge_dist = np.asarray(edge_dist, float)
    ok = edge_dist >= max(edge_buffer, 0.0)
    if zs.size:
        mean, sd = zs.mean(), zs.std()
        if sd > 0:
            ok &= np.abs(zs - mean) <= sd_limit * sd
    cand = np.flatnonzero(ok)
    if cand.size <= n_target:
        return cand

    cz = zs[cand]
    cuts = np.quantile(cz, np.linspace(0, 1, n_strata + 1)[1:-1])
    strata = np.searchsorted(cuts, cz, side="right")

    g = int(math.ceil(math.sqrt(n_target)))
    cx, cy = xs[cand], ys[cand]
    span_x = max(cx.max() - cx.min(), 1e-9)
    span_y = max(cy.max() - cy.min(), 1e-9)
    bx = np.minimum(((cx - cx.min()) / span_x * g).astype(int), g - 1)
    by = np.minimum(((cy - cy.min()) / span_y * g).astype(int), g - 1)
    block = bx * g + by

    rng = np.random.default_rng(seed)
    pools = {}
    for k in rng.permutation(cand.size):
        pools.setdefault(int(block[k]), []).append(int(k))
    counts = np.zeros(n_strata, dtype=int)
    chosen = []
    while len(chosen) < n_target and any(pools.values()):
        for b in rng.permutation(sorted(pools)):
            pool = pools[int(b)]
            if not pool:
                continue
            # take the candidate of this block whose value class is least represented
            j = min(range(len(pool)), key=lambda t: counts[strata[pool[t]]])
            k = pool.pop(j)
            counts[strata[k]] += 1
            chosen.append(k)
            if len(chosen) >= n_target:
                break
    return np.sort(cand[np.array(chosen, dtype=int)])


def cross_validate_idw(xs, ys, zs, val_idx, powers, max_list, exclusion, radius=0.0,
                       min_neighbours=MIN_NEIGHBOURS):
    """
    Cross-validation of IDW with an exclusion zone.

    Each validation sample is predicted from the other samples, ignoring every sample
    closer than ``exclusion`` m (its own sensor-pass neighbours), so the error reflects
    a pixel that is as far from data as a typical pixel of the map. Neighbours follow the
    same rule as the map: within ``radius`` (0 = none), at least ``min_neighbours``, at
    most each value of ``max_list``.

    Returns (rmse, coverage): arrays shaped (len(powers), len(max_list)); ``coverage`` is the
    fraction of validation samples that could be predicted.
    """
    xs, ys, zs = (np.asarray(a, float) for a in (xs, ys, zs))
    powers = np.asarray(powers, float)
    max_list = [int(m) for m in max_list]
    sq = np.zeros((powers.size, len(max_list)))
    hits = np.zeros((powers.size, len(max_list)))
    idx_all = np.arange(xs.size)
    val_idx = np.asarray(val_idx, int)
    for i in val_idx:
        d = np.hypot(xs - xs[i], ys - ys[i])
        keep = np.flatnonzero((d > exclusion) & (idx_all != i))
        if keep.size == 0:
            continue
        order = keep[np.argsort(d[keep])]
        ds = d[order]
        for mj, m in enumerate(max_list):
            used = select_neighbour_distances(ds, radius, min_neighbours, m).size
            if used == 0:
                continue
            w = ds[:used][None, :] ** (-powers[:, None])
            est = (w @ zs[order[:used]]) / w.sum(axis=1)
            sq[:, mj] += (est - zs[i]) ** 2
            hits[:, mj] += 1
    with np.errstate(invalid="ignore", divide="ignore"):
        rmse = np.sqrt(np.where(hits > 0, sq / np.maximum(hits, 1), np.nan))
    coverage = hits / max(val_idx.size, 1)
    return rmse, coverage


def best_combination(rmse, coverage, min_coverage=0.95):
    """(i, j) of the lowest RMSE among combinations covering at least ``min_coverage``."""
    valid = np.isfinite(rmse) & (coverage >= min_coverage)
    if not valid.any():
        valid = np.isfinite(rmse) & (coverage > 0)
    if not valid.any():
        return None
    masked = np.where(valid, rmse, np.inf)
    i, j = np.unravel_index(int(np.argmin(masked)), rmse.shape)
    return int(i), int(j)


CV_POWERS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
CV_MAX_NEIGHBOURS = [4, 8, 12, 16, 24, 32]
CV_MULTIPLES = CV_MAX_NEIGHBOURS          # kept for older imports
CV_N_TARGET = 60
CV_MIN_VALIDATION = 10


def suggest_parameters(xs, ys, zs, edge_dist, coverage, typical, n_target=CV_N_TARGET,
                       pixels=None, pixel_nearest=None):
    """
    Full cross-validation for ONE attribute (each attribute has its own spatial dependence
    and variability, so each gets its own P and maximum of neighbours).

    Tests every power of CV_POWERS with every maximum of CV_MAX_NEIGHBOURS (minimum fixed
    at MIN_NEIGHBOURS, no radius); the exclusion zone is the attribute's typical
    pixel-to-sample distance. The power is then refined in 0.1 steps. The search radius
    is computed so it reaches the chosen maximum in 95 % of the field and the minimum in
    all of it (radius_for_neighbours over the field pixels ``pixels`` = (px, py), or over
    the samples when not given).

    Returns None when the coverage distance is unknown; {"error": ...} when there are too
    few validation samples or nothing works; otherwise a dict with the RMSE table, the
    best cell, power, max_neighbours and radius. ``pixel_nearest`` is accepted for
    compatibility and ignored: the minimum of neighbours already prevents gaps.
    """
    xs, ys, zs = (np.asarray(a, float) for a in (xs, ys, zs))
    if not coverage or coverage <= 0 or zs.size == 0:
        return None
    val = select_validation_samples(xs, ys, zs, edge_dist, n_target=n_target, edge_buffer=coverage)
    if len(val) < CV_MIN_VALIDATION:
        return {"error": "few", "n_val": int(len(val))}
    exclusion = typical or 0.0
    rmse, cov = cross_validate_idw(xs, ys, zs, val, CV_POWERS, CV_MAX_NEIGHBOURS, exclusion)
    best = best_combination(rmse, cov, min_coverage=0.95)
    if best is None:
        return {"error": "failed", "n_val": int(len(val))}
    max_n = CV_MAX_NEIGHBOURS[best[1]]
    fine = np.round(np.arange(STUDENT_POWER_MIN, STUDENT_POWER_MAX + 1e-9, 0.1), 1)
    rf, cf = cross_validate_idw(xs, ys, zs, val, fine, [max_n], exclusion)
    k = best_combination(rf, cf)
    power = float(fine[k[0]]) if k else float(CV_POWERS[best[0]])
    px, py = pixels if pixels is not None else (xs, ys)
    extra = 0 if pixels is not None else 1          # a sample is its own nearest neighbour
    # the radius reaches the maximum in 95 % of the field and the minimum everywhere, so the
    # auto-fit never leaves pixels searching beyond the radius
    radius = max(radius_for_neighbours(px, py, xs, ys, max_n + extra) or 0.0,
                 radius_for_neighbours(px, py, xs, ys, MIN_NEIGHBOURS + extra, q=100.0) or 0.0,
                 float(math.ceil(coverage)))
    return {
        "rmse": rmse, "coverage": cov, "best": best, "power": power,
        "max_neighbours": int(max_n), "min_neighbours": MIN_NEIGHBOURS, "radius": radius,
        "best_rmse": float(rf[k] if k else rmse[best]), "n_val": int(len(val)),
        "exclusion": float(exclusion), "mean": float(np.mean(zs[val])),
    }
