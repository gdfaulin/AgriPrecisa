"""Unit tests for the pure numerical core (no QGIS needed)."""
import math

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


def test_sample_density():
    from agriprecisa.core.idw_math import sample_density
    assert sample_density(50, 25.0) == pytest.approx(2.0)
    assert sample_density(10, 0) is None
    assert sample_density(10, None) is None


def test_mean_spacing_one_sample_per_hectare_is_100m():
    from agriprecisa.core.idw_math import mean_spacing
    assert mean_spacing(1.0) == pytest.approx(100.0)
    assert mean_spacing(4.0) == pytest.approx(50.0)
    assert mean_spacing(0) is None and mean_spacing(None) is None


def test_power_and_radius_bands():
    from agriprecisa.core.idw_math import power_band, radius_band
    assert [power_band(p) for p in (1.0, 1.4, 1.5, 2.0, 2.5, 2.6, 3.0)] == \
        ["low", "low", "mid", "mid", "mid", "high", "high"]
    assert [radius_band(m) for m in (1.0, 1.5, 2.5, 3.0)] == ["short", "ok", "ok", "long"]


def test_relative_weights_decay_faster_with_higher_power():
    from agriprecisa.core.idw_math import relative_weights
    d = [5, 10, 20, 40]
    w1, w3 = relative_weights(d, 1, 5), relative_weights(d, 3, 5)
    assert w1[0] == pytest.approx(1.0) and w3[0] == pytest.approx(1.0)
    assert w1[-1] == pytest.approx(0.125) and w3[-1] == pytest.approx(0.125 ** 3)
    assert all(w3[1:] < w1[1:])


# ------------------------------------------------------------- cross-validation
from agriprecisa.core.idw_math import (
    nearest_distances, coverage_distances, select_validation_samples, cross_validate_idw,
    best_combination,
)


def _grid(n=10, step=10.0):
    g = np.arange(n) * step + step / 2
    xx, yy = np.meshgrid(g, g)
    return xx.ravel(), yy.ravel()


def test_coverage_distance_regular_grid():
    xs, ys = _grid(10, 10.0)                      # samples every 10 m in a 100 x 100 m field
    px, py = _grid(100, 1.0)                      # 1 m pixels
    typical, cover = coverage_distances(px, py, xs, ys)
    assert 3.0 < typical < 4.5                    # mean distance in a 10 m cell ~ 3.8 m
    assert 5.5 < cover < 7.1                      # never beyond the half-diagonal 7.07 m


def test_coverage_distance_sees_gaps_between_sensor_passes():
    # passes every 20 m, points every 1 m along the pass: density is high but the
    # space between passes is wide; coverage must reflect the 10 m gap, not the 1 m spacing
    xs = np.concatenate([np.arange(0, 100, 1.0) for _ in range(5)])
    ys = np.repeat(np.arange(5) * 20.0 + 10, 100)
    px, py = _grid(100, 1.0)
    typical, cover = coverage_distances(px, py, xs, ys)
    assert cover > 8.0
    assert math.sqrt(10000.0 / (500 / 1.0)) < 5.0   # density-based spacing would say ~4.5 m


def test_nearest_distances_no_samples():
    assert np.all(np.isinf(nearest_distances([1.0], [1.0], [], [])))


def test_validation_selection_rules():
    rng = np.random.default_rng(0)
    xs, ys = rng.uniform(0, 1000, 3000), rng.uniform(0, 1000, 3000)
    zs = rng.normal(50, 5, 3000)
    zs[:5] = 500.0                                 # obvious outliers
    edge = np.minimum.reduce([xs, ys, 1000 - xs, 1000 - ys])
    edge[10:20] = -1                               # outside the field
    idx = select_validation_samples(xs, ys, zs, edge, n_target=60, edge_buffer=50)
    assert len(idx) == 60 and len(set(idx)) == 60
    assert not set(idx) & set(range(5))            # outliers excluded
    assert not set(idx) & set(range(10, 20))       # outside excluded
    assert np.all(edge[idx] >= 50)                 # away from the border
    # spread: every quarter of the field is represented
    quad = (xs[idx] > 500).astype(int) * 2 + (ys[idx] > 500).astype(int)
    assert set(quad) == {0, 1, 2, 3}
    # value classes balanced (low / medium / high tertiles of the candidates)
    t1, t2 = np.quantile(zs[5:], [1 / 3, 2 / 3])
    classes = np.searchsorted([t1, t2], zs[idx], side="right")
    assert min(np.bincount(classes, minlength=3)) >= 15
    # reproducible
    assert np.array_equal(idx, select_validation_samples(xs, ys, zs, edge, 60, 50))


def test_validation_keeps_extremes_unlike_one_sd_rule():
    rng = np.random.default_rng(1)
    xs, ys = rng.uniform(0, 1000, 2000), rng.uniform(0, 1000, 2000)
    zs = rng.normal(0, 1, 2000)
    idx = select_validation_samples(xs, ys, zs, np.full(2000, 500.0), n_target=60)
    assert np.abs(zs[idx]).max() > 1.5             # values beyond 1 SD are represented


def test_cross_validation_constant_field_has_zero_error():
    xs, ys = _grid(8, 10.0)
    zs = np.full(xs.size, 7.0)
    rmse, cov = cross_validate_idw(xs, ys, zs, [10, 20, 30], [1, 2, 3], [15, 30], exclusion=0.0)
    assert np.allclose(rmse, 0.0) and np.allclose(cov, 1.0)


def test_cross_validation_never_uses_the_sample_itself():
    xs, ys = np.array([0.0, 10.0]), np.array([0.0, 0.0])
    zs = np.array([1.0, 5.0])
    rmse, cov = cross_validate_idw(xs, ys, zs, [0], [2], [100], exclusion=0.0)
    assert rmse[0, 0] == pytest.approx(4.0)        # predicted only from the other sample


def test_exclusion_zone_ignores_close_neighbours():
    # validation point at 0 m; a near-duplicate at 1 m (same pass) and a sample at 30 m
    xs, ys = np.array([0.0, 1.0, 30.0]), np.zeros(3)
    zs = np.array([10.0, 10.0, 20.0])
    no_excl, _ = cross_validate_idw(xs, ys, zs, [0], [2], [100], exclusion=0.0)
    with_excl, _ = cross_validate_idw(xs, ys, zs, [0], [2], [100], exclusion=5.0)
    assert no_excl[0, 0] < 0.05                    # optimistic: neighbour repeats the value
    assert with_excl[0, 0] == pytest.approx(10.0)  # realistic: only the 30 m sample is used


def test_radius_without_neighbours_has_no_coverage():
    xs, ys = np.array([0.0, 50.0]), np.zeros(2)
    rmse, cov = cross_validate_idw(xs, ys, np.array([1.0, 2.0]), [0], [2], [10, 100], 0.0)
    assert np.isnan(rmse[0, 0]) and cov[0, 0] == 0 and cov[0, 1] == 1


def test_best_combination_prefers_covered_minimum():
    rmse = np.array([[1.0, 0.5], [0.2, 0.9]])
    cov = np.array([[1.0, 1.0], [0.5, 1.0]])       # 0.2 has poor coverage
    assert best_combination(rmse, cov) == (0, 1)
