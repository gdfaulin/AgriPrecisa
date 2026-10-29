"""Unit tests for the pure numerical core (no QGIS needed)."""
import numpy as np
import pytest

from agriprecisa.core.idw_math import NODATA, idw_grid, safe_name, snap_extent, unique_prefixes


def test_pixel_on_sample_takes_sample_value():
    g = idw_grid([0.0, 10.0], [0.0, 0.0], [1.0, 3.0], -0.5, 0.5, 1, 1, 1.0, 2, 0)
    assert g[0, 0] == pytest.approx(1.0)


def test_midpoint_is_average_for_equal_distances():
    g = idw_grid([0.0, 10.0], [0.0, 0.0], [1.0, 3.0], 4.5, 0.5, 1, 1, 1.0, 2, 0)
    assert g[0, 0] == pytest.approx(2.0)


def test_known_weights_power_2():
    # pixel centre (2, 0): distances 2 and 8 -> weights 1/4 and 1/64
    g = idw_grid([0.0, 10.0], [0.0, 0.0], [1.0, 3.0], 1.5, 0.5, 1, 1, 1.0, 2, 0)
    expected = (1 / 4 * 1 + 1 / 64 * 3) / (1 / 4 + 1 / 64)
    assert g[0, 0] == pytest.approx(expected)


def test_radius_leaves_far_pixels_nodata():
    # sample at the corner (0, 0): only the centre (5, 5), 7.07 m away, is within 8 m
    g = idw_grid([0.0], [0.0], [5.0], 0.0, 30.0, 3, 3, 10.0, 2, 8)
    assert (g == NODATA).sum() == 8
    assert g[2, 0] == pytest.approx(5.0)
    g = idw_grid([5.0], [25.0], [5.0], 0.0, 30.0, 3, 3, 10.0, 2, 8)
    assert g[0, 0] == pytest.approx(5.0)
    assert g[2, 2] == NODATA


def test_radius_zero_uses_all_samples():
    g = idw_grid([0.0], [0.0], [7.0], 1000.0, 1000.0, 2, 2, 10.0, 2, 0)
    assert np.all(g == pytest.approx(7.0))


def test_constant_field_stays_constant():
    rng = np.random.default_rng(1)
    xs, ys = rng.uniform(0, 100, 30), rng.uniform(0, 100, 30)
    g = idw_grid(xs, ys, np.full(30, 4.2), 0, 100, 20, 20, 5.0, 2, 0)
    assert np.allclose(g, 4.2)


def test_values_within_sample_range():
    rng = np.random.default_rng(2)
    xs, ys, zs = rng.uniform(0, 100, 40), rng.uniform(0, 100, 40), rng.uniform(10, 50, 40)
    g = idw_grid(xs, ys, zs, 0, 100, 20, 20, 5.0, 2, 0)
    assert g.min() >= zs.min() - 1e-9 and g.max() <= zs.max() + 1e-9


def test_block_processing_matches_single_block():
    # many samples force several blocks; result must not depend on the block size
    rng = np.random.default_rng(3)
    n = 50_000
    xs, ys, zs = rng.uniform(0, 100, n), rng.uniform(0, 100, n), rng.uniform(0, 1, n)
    g = idw_grid(xs, ys, zs, 0, 100, 12, 12, 100 / 12, 2, 0)
    gx = np.arange(12) * 100 / 12 + 50 / 12
    d2 = (gx[3] - xs) ** 2 + ((100 - gx[5]) - ys) ** 2
    w = d2 ** -1
    assert g[5, 3] == pytest.approx((w @ zs) / w.sum())


def test_cancel_returns_none():
    g = idw_grid([0.0], [0.0], [1.0], 0, 10, 10, 10, 1.0, 2, 0, callback=lambda f: False)
    assert g is None


def test_no_samples_all_nodata():
    g = idw_grid([], [], [], 0, 10, 2, 2, 5.0, 2, 0)
    assert np.all(g == NODATA)


def test_snap_extent_outward_to_pixel():
    assert snap_extent(1.0, 2.0, 12.0, 13.0, 5.0) == (0.0, 0.0, 15.0, 15.0, 3, 3)


def test_snap_extent_rejects_bad_pixel():
    with pytest.raises(ValueError):
        snap_extent(0, 0, 1, 1, 0)


def test_safe_name_removes_accents_and_symbols():
    assert safe_name("Potássio (mg/dm³)") == "Potassio_mg_dm3"
    assert safe_name("%%%") == "field"


def test_unique_prefixes_repeated_field_gets_layer_name():
    out = unique_prefixes([("Coleta 2025", "pH"), ("Coleta 2026", "pH"), ("Coleta 2026", "argila")])
    assert out == ["Coleta_2025_pH", "Coleta_2026_pH", "argila"]
    assert len(set(out)) == 3
