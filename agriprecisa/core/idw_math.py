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
