# -*- coding: utf-8 -*-
"""
AgriPrecisa: plant height statistics per row segment and per plant, from the plant height
raster of the DTM tool. Pure numpy/scipy, no QGIS imports (unit-tested with pytest).

Coordinates: ``gt`` is a GDAL geotransform without rotation; pixel centres are
x = gt[0] + (col + 0.5) * gt[1] and y = gt[3] + (row + 0.5) * gt[5].

Rows: the direction of the rows is the angle at which the share of plant pixels, projected
across the rows, oscillates the most (a regular comb of rows); the row centres are the
comb of spacing ``s`` and phase ``phi`` that best matches that profile. Every pixel then has
u (across the rows) and v (along the rows): row k = round((u - phi) / s).
"""

import math

import numpy as np

# minimum distance between plant tops (m), per crop key of mdt_math.CROPS
PLANT_DISTANCE = {"coffee": 0.8, "citrus": 3.0, "maize": 0.2, "soybean": 0.1,
                  "sugarcane": 0.3, "grapevine": 1.0, "eucalyptus": 2.0}
DEFAULT_SEGMENT = 5.0       # m, length of the row segments
MAX_SAMPLES = 250000        # plant/valid pixels used to find the row direction


def plant_distance(crop_key, spacing):
    """Minimum distance between plant tops for a crop (custom: a quarter of the spacing)."""
    return PLANT_DISTANCE.get(crop_key, round(max(spacing / 4.0, 0.1), 2))


def min_gap_length(distance, pixel):
    """A gap (failure) is a stretch of row without plants longer than twice the plant distance."""
    return max(2.0 * distance, 2.0 * pixel)


def plant_threshold(tolerance):
    """Height above which a pixel counts as plant (twice the soil tolerance, at least 0.1 m)."""
    return max(2.0 * tolerance, 0.1)


def _centres(shape, gt):
    rows, cols = np.indices(shape)
    return gt[0] + (cols + 0.5) * gt[1], gt[3] + (rows + 0.5) * gt[5]


def _fraction_profile(u, plant, pixel):
    """Share of plant pixels in bins of one pixel across the rows (bins with data only)."""
    b = np.floor((u - u.min()) / pixel).astype(np.int64)
    total = np.bincount(b)
    plants = np.bincount(b, weights=plant.astype("float64"), minlength=total.size)
    ok = total >= max(3, np.median(total[total > 0]) * 0.2) if total.any() else total > 0
    prof = np.where(ok, plants / np.maximum(total, 1), np.nan)
    return prof, u.min()


def _comb_score(profile, pixel, spacing):
    """Strength of a periodic signal of period ``spacing`` in the profile (0 = none)."""
    p = profile[np.isfinite(profile)]
    if p.size < 4 or p.std() == 0:
        return 0.0
    idx = np.nonzero(np.isfinite(profile))[0] * pixel
    p = p - p.mean()
    w = 2 * math.pi / spacing
    return float(math.hypot(np.sum(p * np.cos(w * idx)), np.sum(p * np.sin(w * idx))) / p.size)


def row_direction(plant, valid, gt, spacing, rng=None):
    """
    Angle theta (radians, 0..pi) of the direction ACROSS the rows, where
    u = x cos(theta) + y sin(theta). Returns (theta, score); score near 0 means no rows found.
    """
    pixel = abs(gt[1])
    x, y = _centres(plant.shape, gt)
    sel = np.flatnonzero(valid.ravel())
    if sel.size == 0:
        return 0.0, 0.0
    if sel.size > MAX_SAMPLES:
        rng = rng or np.random.default_rng(0)
        sel = rng.choice(sel, MAX_SAMPLES, replace=False)
    xs, ys, ps = x.ravel()[sel], y.ravel()[sel], plant.ravel()[sel]

    def score(theta):
        u = xs * math.cos(theta) + ys * math.sin(theta)
        prof, _ = _fraction_profile(u, ps, pixel)
        return _comb_score(prof, pixel, spacing)

    coarse = np.radians(np.arange(0.0, 180.0, 1.0))
    scores = [score(t) for t in coarse]
    best = float(coarse[int(np.argmax(scores))])
    fine = best + np.radians(np.arange(-1.0, 1.01, 0.1))
    fscores = [score(t) for t in fine]
    theta = float(fine[int(np.argmax(fscores))]) % math.pi
    return theta, float(max(fscores))


def row_comb(plant, valid, gt, theta, spacing):
    """
    Refined spacing s (searched from 0.85 to 1.15 x spacing) and phase phi of the row centres:
    the centre of row k is at u = phi + k * s. Returns (s, phi).
    """
    pixel = abs(gt[1])
    x, y = _centres(plant.shape, gt)
    u = (x * math.cos(theta) + y * math.sin(theta))[valid]
    prof, u0 = _fraction_profile(u, plant[valid], pixel)
    best = (-1.0, spacing)
    for s in np.linspace(0.85 * spacing, 1.15 * spacing, 61):
        sc = _comb_score(prof, pixel, s)
        if sc > best[0]:
            best = (sc, float(s))
    s = best[1]
    finite = np.isfinite(prof)
    pos = np.nonzero(finite)[0] * pixel
    p = prof[finite] - prof[finite].mean()
    w = 2 * math.pi / s
    phase = math.atan2(np.sum(p * np.sin(w * pos)), np.sum(p * np.cos(w * pos)))
    phi = u0 + (phase / w) % s
    return s, float(phi)


def row_segments(height, valid, gt, theta, s, phi, segment, plant_min, min_gap):
    """
    Statistics per row segment. Each row k owns the band |u - (phi + k s)| <= s / 2, cut along
    the row in segments of ``segment`` metres. Returns a list of dicts with: row, segment,
    corners [(x, y) x 4], mean, p95, max (plant pixels only), coverage (share of the segment
    length with plants, 0..1), gap (metres of failures: stretches without plants longer than
    ``min_gap`` between plants of the same row), length (m with data), n_plant (plant pixels).
    """
    pixel = abs(gt[1])
    x, y = _centres(height.shape, gt)
    c, sn = math.cos(theta), math.sin(theta)
    xv, yv, hv = x[valid], y[valid], height[valid]
    if hv.size == 0:
        return []
    u = xv * c + yv * sn
    v = -xv * sn + yv * c
    k = np.round((u - phi) / s).astype(np.int64)
    vmin = v.min()
    vb = np.floor((v - vmin) / pixel).astype(np.int64)           # along-row bins of 1 pixel
    seg = np.floor((v - vmin) / segment).astype(np.int64)
    is_plant = np.isfinite(hv) & (hv >= plant_min)
    kmin = k.min()
    kk = k - kmin
    nk, nb = int(kk.max()) + 1, int(vb.max()) + 1
    seg_of_bin = np.floor(np.arange(nb) * pixel / segment).astype(np.int64)
    nseg = int(seg.max()) + 1

    # occupancy of each along-row bin of each row
    valid_bins = np.zeros((nk, nb), bool)
    valid_bins[kk, vb] = True
    occ_bins = np.zeros((nk, nb), bool)
    occ_bins[kk[is_plant], vb[is_plant]] = True

    # failures: runs of valid bins without plants longer than min_gap, between plants of the
    # same row (empty ends of a row, such as headlands, are not failures)
    gap_m = np.zeros((nk, nseg))
    for r in range(nk):
        occ_idx = np.flatnonzero(occ_bins[r])
        if occ_idx.size < 2:
            continue
        empty = valid_bins[r] & ~occ_bins[r]
        empty[:occ_idx[0]] = False
        empty[occ_idx[-1] + 1:] = False
        if not empty.any():
            continue
        d = np.diff(np.concatenate(([0], empty.astype(np.int8), [0])))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        for a, b in zip(starts, ends):
            if (b - a) * pixel >= min_gap:
                np.add.at(gap_m[r], seg_of_bin[a:b], pixel)

    # per segment: plant heights
    key = kk * nseg + seg
    order = np.argsort(key, kind="stable")
    key_sorted = key[order]
    bounds = np.flatnonzero(np.diff(key_sorted)) + 1
    groups = np.split(order, bounds)
    out = []
    row_numbers = {}
    for g in groups:
        kq = int(kk[g[0]])
        sq = int(seg[g[0]])
        vb_seg = valid_bins[kq][seg_of_bin == sq]
        n_len = int(vb_seg.sum())
        if n_len == 0:
            continue
        occ = int((occ_bins[kq][seg_of_bin == sq] & vb_seg).sum())
        hp = hv[g][is_plant[g]]
        uc = phi + (kq + kmin) * s
        v0 = vmin + sq * segment
        v1 = min(v0 + segment, vmin + nb * pixel)
        corners = [(uu * c - vv * sn, uu * sn + vv * c)
                   for uu, vv in ((uc - s / 2, v0), (uc + s / 2, v0), (uc + s / 2, v1), (uc - s / 2, v1))]
        row_numbers.setdefault(kq, None)
        out.append({
            "k": kq, "segment": sq, "corners": corners,
            "mean": float(hp.mean()) if hp.size else 0.0,
            "p95": float(np.percentile(hp, 95)) if hp.size else 0.0,
            "max": float(hp.max()) if hp.size else 0.0,
            "coverage": occ / n_len,
            "gap": float(gap_m[kq, sq]),
            "length": n_len * pixel,
            "n_plant": int(hp.size),
        })
    # rows numbered 1, 2, 3... in the u direction; segments 1, 2, 3... along each row
    ks = sorted({o["k"] for o in out})
    number = {kq: i + 1 for i, kq in enumerate(ks)}
    for o in out:
        o["row"] = number[o.pop("k")]
        o["segment"] = o["segment"] + 1
    out.sort(key=lambda o: (o["row"], o["segment"]))
    return out


def detect_plants(height, valid, gt, distance, plant_min):
    """
    Plant tops (local maxima of the smoothed height, at least ``distance`` apart) and crowns
    (plant pixels of the same connected patch assigned to the nearest top).
    Returns (plants, crowns): plants is a list of dicts (id, x, y, height, mean, area,
    diameter); crowns is an int32 raster with the plant id of each crown pixel (0 = none).
    """
    from scipy import ndimage
    pixel = abs(gt[1])
    h = np.where(valid & np.isfinite(height), height, 0.0)
    plant = h >= plant_min
    sigma = max(0.5, 0.25 * distance / pixel)
    smooth = ndimage.gaussian_filter(h, sigma)
    size = max(3, int(round(distance / pixel)) | 1)
    peaks = (smooth == ndimage.maximum_filter(smooth, size=size)) & plant
    lab, n = ndimage.label(peaks)
    crowns = np.zeros(h.shape, np.int32)
    if n == 0:
        return [], crowns
    centres = ndimage.center_of_mass(peaks, lab, range(1, n + 1))
    tops = np.array([(int(round(r)), int(round(cc))) for r, cc in centres])
    # a top must lie on a plant pixel; drop flat-plateau centres that fall outside
    keep = plant[tops[:, 0], tops[:, 1]]
    tops = tops[keep]
    if tops.size == 0:
        return [], crowns
    markers = np.zeros(h.shape, np.int32)
    markers[tops[:, 0], tops[:, 1]] = np.arange(1, len(tops) + 1)
    patches, _ = ndimage.label(plant)
    _, (ir, ic) = ndimage.distance_transform_edt(markers == 0, return_indices=True)
    nearest = markers[ir, ic]
    same_patch = patches == patches[ir, ic]
    crowns = np.where(plant & same_patch, nearest, 0).astype(np.int32)

    ids = np.arange(1, len(tops) + 1)
    area = ndimage.sum(np.ones_like(h), crowns, ids) * pixel * pixel
    mean = ndimage.mean(h, crowns, ids)
    hmax = ndimage.maximum(h, crowns, ids)
    plants = []
    for i, (r, cc) in enumerate(tops):
        a = float(area[i])
        plants.append({
            "id": i + 1,
            "x": gt[0] + (cc + 0.5) * gt[1], "y": gt[3] + (r + 0.5) * gt[5],
            "height": float(hmax[i]), "mean": float(mean[i]),
            "area": a, "diameter": 2.0 * math.sqrt(a / math.pi),
        })
    return plants, crowns
