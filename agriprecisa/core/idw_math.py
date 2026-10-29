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


def idw_grid(xs, ys, zs, xmin, ymax, ncol, nrow, res, power, radius, callback=None):
    """
    Inverse Distance Weighting evaluated at each pixel centre.

    value = sum(z / d^P) / sum(1 / d^P), using only samples within ``radius``.
    ``radius`` = 0 means all samples are used. Pixels with no sample within
    the radius receive NODATA. A pixel lying exactly on a sample takes that
    sample's value (mean if several samples coincide).

    ``callback(fraction)`` may return False to cancel; the function then
    returns None. Work is done in blocks to bound memory use.
    """
    xs = np.asarray(xs, dtype=np.float64)
    ys = np.asarray(ys, dtype=np.float64)
    zs = np.asarray(zs, dtype=np.float64)

    cx = xmin + (np.arange(ncol) + 0.5) * res
    cy = ymax - (np.arange(nrow) + 0.5) * res
    gx, gy = np.meshgrid(cx, cy)
    gx, gy = gx.ravel(), gy.ravel()

    out = np.full(gx.size, NODATA, dtype=np.float64)
    n = xs.size
    if n == 0:
        return out.reshape(nrow, ncol)

    block = max(1, int(4_000_000 // n))
    r2 = radius * radius if radius > 0 else None

    for start in range(0, gx.size, block):
        end = min(start + block, gx.size)
        dx = gx[start:end, None] - xs[None, :]
        dy = gy[start:end, None] - ys[None, :]
        d2 = dx * dx + dy * dy

        valid = (d2 <= r2) if r2 is not None else np.ones_like(d2, dtype=bool)
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
    return out.reshape(nrow, ncol)


def sample_density(n_samples, area_ha):
    """Samples per hectare; None when the area is not positive."""
    if area_ha is None or area_ha <= 0:
        return None
    return n_samples / area_ha


# ---------------------------------------------------------------------------
# Helpers for the didactic (student mode) parameter page
# ---------------------------------------------------------------------------
STUDENT_POWER_MIN, STUDENT_POWER_MAX = 1.0, 3.0
STUDENT_RADIUS_MIN, STUDENT_RADIUS_MAX = 1.0, 4.0   # multiples of the sample spacing
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


def relative_weights(distances, power, d_min):
    """IDW weight relative to a sample at ``d_min`` metres: (d_min / d)^P, capped at 1."""
    d = np.maximum(np.asarray(distances, dtype=float), d_min)
    return (d_min / d) ** power
