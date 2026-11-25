"""Plant height statistics per row segment and per plant (core/mdt_stats.py), no QGIS."""
import math

import numpy as np
import pytest

from agriprecisa.core import mdt_stats as ms

PIXEL = 0.2
GT = (500000.0, PIXEL, 0.0, 7500000.0, 0.0, -PIXEL)


def orchard(angle_deg=30.0, spacing=4.0, plant_step=2.5, radius=0.9, top=2.0, n=400,
            missing=True):
    """Height raster with dome-shaped crowns on rows at ``angle_deg`` (direction across rows)."""
    rows, cols = np.indices((n, n))
    x = GT[0] + (cols + 0.5) * PIXEL
    y = GT[3] + (rows + 0.5) * GT[5]
    t = math.radians(angle_deg)
    u = x * math.cos(t) + y * math.sin(t)
    v = -x * math.sin(t) + y * math.cos(t)
    k = np.round(u / spacing)
    j = np.round(v / plant_step)
    du, dv = u - k * spacing, v - j * plant_step
    d = np.hypot(du, dv)
    h = np.where(d < radius, top * np.sqrt(np.clip(1 - (d / radius) ** 2, 0, 1)), 0.0)
    if missing:                                  # three plants missing in the central row
        kc, jc = k[n // 2, n // 2], j[n // 2, n // 2]
        for jj in (jc - 1, jc, jc + 1):
            h[(k == kc) & (j == jj)] = 0.0
    return h, k, j


def test_row_direction_and_spacing_found():
    h, _, _ = orchard()
    valid = np.ones(h.shape, bool)
    theta, score = ms.row_direction(h >= 0.3, valid, GT, 4.0)
    ang = math.degrees(theta) % 180
    assert min(abs(ang - 30), abs(ang - 210 % 180)) < 1.0
    assert score > 0.05
    s, phi = ms.row_comb(h >= 0.3, valid, GT, theta, 4.0)
    assert s == pytest.approx(4.0, abs=0.05)
    # the comb lands on the row centres (u multiple of the spacing)
    assert min(phi % 4.0, 4.0 - phi % 4.0) < 0.15


def test_row_segments_heights_coverage_and_failures():
    h, _, _ = orchard()
    valid = np.ones(h.shape, bool)
    theta, _ = ms.row_direction(h >= 0.3, valid, GT, 4.0)
    s, phi = ms.row_comb(h >= 0.3, valid, GT, theta, 4.0)
    segs = ms.row_segments(h, valid, GT, theta, s, phi, 5.0, 0.3, ms.min_gap_length(1.0, PIXEL))
    full = [o for o in segs if o["length"] >= 4.9]
    assert full
    # crowns of 1.8 m every 2.5 m: about 72 percent of the row length covered
    cov = np.median([o["coverage"] for o in full])
    assert 0.6 < cov < 0.85
    assert np.median([o["p95"] for o in full]) == pytest.approx(1.9, abs=0.2)
    # the three missing plants give failures of several metres in exactly one row
    rows_with_gaps = {o["row"] for o in segs if o["gap"] >= 3.0}
    assert len(rows_with_gaps) == 1
    total_gap = sum(o["gap"] for o in segs if o["row"] in rows_with_gaps)
    assert 7.0 < total_gap < 9.5           # 4 x 2.5 m minus one crown width

    # segment polygons have the row spacing as width and at most the segment length
    o = full[0]
    (x0, y0), (x1, y1), (x2, y2), _ = o["corners"]
    assert math.hypot(x1 - x0, y1 - y0) == pytest.approx(s, abs=1e-6)
    assert math.hypot(x2 - x1, y2 - y1) <= 5.0 + 1e-6


def test_empty_row_ends_are_not_failures():
    # Rows that start late (headland): the empty stretch before the first plant is no failure
    h, _, _ = orchard(missing=False)
    h[:, :150] = 0.0                       # no plants in the first 30 m, but data present
    valid = np.ones(h.shape, bool)
    theta, _ = ms.row_direction(h >= 0.3, valid, GT, 4.0)
    s, phi = ms.row_comb(h >= 0.3, valid, GT, theta, 4.0)
    segs = ms.row_segments(h, valid, GT, theta, s, phi, 5.0, 0.3, 2.0)
    assert max(o["gap"] for o in segs) < 2.0


def test_detect_plants_counts_crowns_and_heights():
    h, k, j = orchard(missing=False)
    valid = np.ones(h.shape, bool)
    plants, crowns = ms.detect_plants(h, valid, GT, 2.0, 0.3)
    # whole crowns inside the raster (away from the border)
    rows, cols = np.indices(h.shape)
    inner = (rows > 10) & (rows < h.shape[0] - 10) & (cols > 10) & (cols < h.shape[1] - 10)
    expected = len({(a, b) for a, b in zip(k[inner & (h > 1.5)], j[inner & (h > 1.5)])})
    found = [p for p in plants if 10 * PIXEL < p["x"] - GT[0] < (h.shape[1] - 10) * PIXEL
             and 10 * PIXEL < GT[3] - p["y"] < (h.shape[0] - 10) * PIXEL]
    assert abs(len(found) - expected) <= max(2, 0.05 * expected)
    heights = [p["height"] for p in found]
    assert np.median(heights) == pytest.approx(2.0, abs=0.1)
    diam = np.median([p["diameter"] for p in found])
    assert 1.2 < diam < 2.0                    # crowns of 1.8 m above the 0.3 m threshold
    assert crowns.max() == len(plants)


def test_no_plants_and_helpers():
    h = np.zeros((50, 50))
    plants, crowns = ms.detect_plants(h, np.ones(h.shape, bool), GT, 1.0, 0.3)
    assert plants == [] and crowns.max() == 0
    assert ms.plant_distance("citrus", 6.5) == 3.0
    assert ms.plant_distance("custom", 2.0) == 0.5
    assert ms.min_gap_length(0.8, 0.25) == 1.6
    assert ms.plant_threshold(0.25) == 0.5
    assert ms.plant_threshold(0.02) == 0.1
