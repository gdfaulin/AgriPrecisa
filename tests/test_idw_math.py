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


def test_radius_gap_uses_nearest_samples_instead_of_nodata():
    # Regression: pixels in a gap between sensor passes wider than the search radius were
    # left without value (NODATA) and the grid cells over them came out blank.
    xs = np.array([0.0, 0.0, 30.0, 30.0])
    ys = np.array([0.0, 10.0, 0.0, 10.0])
    zs = np.array([1.0, 1.0, 3.0, 3.0])
    # pixel at x = 15 is 15 m from every sample; radius 5 m reaches none of them
    g, used = idw_grid(xs, ys, zs, 12.5, 7.5, 1, 1, 5.0, 2, 5.0, return_fallback=True)
    assert g[0, 0] != NODATA and used[0, 0]
    assert g[0, 0] == pytest.approx(2.0)          # 4 nearest, symmetric -> mean of 1 and 3
    # pixels where the radius reaches the minimum are not flagged
    g2, used2 = idw_grid(xs, ys, zs, -2.5, 2.5, 1, 1, 5.0, 2, 5.0, min_neighbours=1,
                         return_fallback=True)
    assert not used2[0, 0]
    # with the default minimum (4) the same pixel reaches only 1 sample and goes beyond
    _, used3 = idw_grid(xs, ys, zs, -2.5, 2.5, 1, 1, 5.0, 2, 5.0, return_fallback=True)
    assert used3[0, 0]


def test_radius_leaves_far_pixels_nodata():
    # sample at the corner (0, 0): only the centre (5, 5), 7.07 m away, is within 8 m
    g = idw_grid([0.0], [0.0], [5.0], 0.0, 30.0, 3, 3, 10.0, 2, 8, fallback_neighbours=0)
    assert (g == NODATA).sum() == 8
    assert g[2, 0] == pytest.approx(5.0)
    g = idw_grid([5.0], [25.0], [5.0], 0.0, 30.0, 3, 3, 10.0, 2, 8, fallback_neighbours=0)
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
    assert [power_band(p) for p in (0.5, 1.0, 1.4, 1.5, 2.0, 2.5, 2.6, 5.0)] == \
        ["low", "low", "low", "mid", "mid", "mid", "high", "high"]
    assert [radius_band(m) for m in (1.0, 1.5, 2.5, 3.0)] == ["short", "ok", "ok", "long"]


def test_relative_weight_is_one_at_reference_and_infinite_at_zero():
    # Regression: the chart showed weight 1 at distance 0 (a flat plateau); in IDW the
    # weight 1/d^P grows without limit as d -> 0 (Shepard, 1968)
    from agriprecisa.core.idw_math import relative_weights
    w = relative_weights([0.0, 2.0, 4.0, 8.0], 2, d_ref=4.0)
    assert np.isinf(w[0])
    assert w[1] == pytest.approx(4.0) and w[2] == pytest.approx(1.0) and w[3] == pytest.approx(0.25)
    w1, w3 = relative_weights([8.0], 1, 4.0), relative_weights([8.0], 3, 4.0)
    assert w3[0] < w1[0]                           # higher P: faster decay


def test_normalized_weights_sum_to_one_and_concentrate_with_p():
    from agriprecisa.core.idw_math import normalized_weights
    d = [2.0, 4.0, 6.0, 8.0]
    l1, l3 = normalized_weights(d, 1), normalized_weights(d, 3)
    assert l1.sum() == pytest.approx(1.0) and l3.sum() == pytest.approx(1.0)
    assert l1[0] == pytest.approx((1 / 2) / (1 / 2 + 1 / 4 + 1 / 6 + 1 / 8))
    assert l3[0] > l1[0]                           # P = 3 gives more to the nearest sample
    assert list(normalized_weights([0.0, 5.0], 2)) == [1.0, 0.0]
    assert normalized_weights([], 2).size == 0


def test_typical_pixel_neighbours():
    from agriprecisa.core.idw_math import typical_pixel_neighbours
    xs, ys = _grid(10, 10.0)
    px, py = _grid(100, 1.0)
    d = typical_pixel_neighbours(px, py, xs, ys, radius=20.0)
    assert d.size >= 4 and np.all(np.diff(d) >= 0) and d.max() <= 20.0
    assert typical_pixel_neighbours(px, py, xs, ys, 20.0, max_neighbours=3).size == 3


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


def test_cross_validation_minimum_neighbours_beyond_radius():
    # with a 10 m radius nothing is reachable, but the minimum of neighbours still predicts
    xs, ys = np.array([0.0, 50.0]), np.zeros(2)
    rmse, cov = cross_validate_idw(xs, ys, np.array([1.0, 2.0]), [0], [2], [4, 8], 0.0, radius=10.0)
    assert np.allclose(cov, 1.0) and rmse[0, 0] == pytest.approx(1.0)
    none, cov0 = cross_validate_idw(xs, ys, np.array([1.0, 2.0]), [0], [2], [4], 0.0, radius=10.0,
                                    min_neighbours=0)
    assert np.isnan(none[0, 0]) and cov0[0, 0] == 0


def test_cross_validation_maximum_limits_neighbours():
    # validation at 0; neighbours at 10 m (value 10) and 20, 30, 40 m (value 0)
    xs, ys = np.array([0.0, 10.0, 20.0, 30.0, 40.0]), np.zeros(5)
    zs = np.array([10.0, 10.0, 0.0, 0.0, 0.0])
    rmse, _ = cross_validate_idw(xs, ys, zs, [0], [2], [1, 4], 0.0, min_neighbours=1)
    assert rmse[0, 0] == pytest.approx(0.0)        # only the nearest (same value)
    assert rmse[0, 1] > 1.0                        # the far ones pull the estimate down


def test_best_combination_prefers_covered_minimum():
    rmse = np.array([[1.0, 0.5], [0.2, 0.9]])
    cov = np.array([[1.0, 1.0], [0.5, 1.0]])       # 0.2 has poor coverage
    assert best_combination(rmse, cov) == (0, 1)


def test_suggest_parameters_differs_between_attributes():
    # two attributes on the same sensor passes: one smooth (long-range dependence) and one
    # with strong short-range variation; each must get its own parameters
    from agriprecisa.core.idw_math import suggest_parameters, coverage_distances, CV_MAX_NEIGHBOURS
    rng = np.random.default_rng(3)
    xs = np.concatenate([np.arange(0, 300, 2.0) for _ in range(15)])
    ys = np.repeat(np.arange(15) * 20.0 + 10, 150)
    smooth = 2 + xs / 150 + rng.normal(0, 0.02, xs.size)
    rough = np.sin(xs / 6.0) * np.cos(ys / 7.0) + rng.normal(0, 0.02, xs.size)
    edge = np.minimum.reduce([xs, ys, 300 - xs, 300 - ys])
    px, py = _grid(60, 5.0)
    typical, cover = coverage_distances(px, py, xs, ys)
    a = suggest_parameters(xs, ys, smooth, edge, cover, typical, pixels=(px, py))
    b = suggest_parameters(xs, ys, rough, edge, cover, typical, pixels=(px, py))
    assert a["n_val"] == 60 and b["n_val"] == 60
    assert a["max_neighbours"] in CV_MAX_NEIGHBOURS and b["max_neighbours"] in CV_MAX_NEIGHBOURS
    assert (a["power"], a["max_neighbours"]) != (b["power"], b["max_neighbours"])
    # a smooth field gains from more neighbours (or a lower P) than a rough one
    assert a["max_neighbours"] >= b["max_neighbours"] or a["power"] < b["power"]


def test_suggest_parameters_few_samples():
    from agriprecisa.core.idw_math import suggest_parameters
    xs, ys = _grid(3, 10.0)
    r = suggest_parameters(xs, ys, np.arange(9.0), np.full(9, 100.0), 7.0, 3.0)
    assert r == {"error": "few", "n_val": 9}


def test_suggested_radius_does_not_cut_the_maximum_of_neighbours():
    # the radius set by the auto-fit must reach the chosen maximum in 95 % of the field, so
    # the maximum (not the radius) decides how many samples a pixel uses
    from agriprecisa.core.idw_math import (suggest_parameters, coverage_distances,
                                           kth_nearest_distances)
    rng = np.random.default_rng(3)
    xs = np.concatenate([np.arange(0, 300, 2.0) for _ in range(15)])
    ys = np.repeat(np.arange(15) * 20.0 + 10, 150)
    rough = np.sin(xs / 6.0) * np.cos(ys / 7.0) + rng.normal(0, 0.02, xs.size)
    edge = np.minimum.reduce([xs, ys, 300 - xs, 300 - ys])
    px, py = _grid(130, 2.3)                                 # fine pixels, not aligned to passes
    typical, cover = coverage_distances(px, py, xs, ys)
    r = suggest_parameters(xs, ys, rough, edge, cover, typical, pixels=(px, py))
    kth = kth_nearest_distances(px, py, xs, ys, r["max_neighbours"])
    assert np.mean(kth <= r["radius"]) >= 0.95
    assert r["radius"] >= cover
    # Regression: with a maximum of 4, 5 % of the field reached fewer than the minimum and
    # step 3 showed the orange warning right after the auto-fit
    k4 = kth_nearest_distances(px, py, xs, ys, 4)
    assert (k4 <= r["radius"]).all()


def test_minimum_neighbours_is_always_met_beyond_radius():
    # every pixel has a value even with a tiny radius; flagged pixels went beyond it
    rng = np.random.default_rng(5)
    xs, ys, zs = rng.uniform(0, 100, 40), rng.uniform(0, 100, 40), rng.uniform(0, 10, 40)
    g, used = idw_grid(xs, ys, zs, 0, 100, 20, 20, 5.0, 2, 1.0, max_neighbours=16,
                       return_fallback=True)
    assert (g != NODATA).all() and used.mean() > 0.9


def test_maximum_neighbours_limits_the_radius():
    # pixel at x = 0: samples at 1 m (value 10) and 50 m (value 0, nine of them)
    xs = np.array([1.0] + [50.0] * 9)
    ys = np.array([0.0] + list(np.linspace(-1, 1, 9)))
    zs = np.array([10.0] + [0.0] * 9)
    all_n = idw_grid(xs, ys, zs, -0.5, 0.5, 1, 1, 1.0, 1, 0, min_neighbours=1, max_neighbours=0)
    one = idw_grid(xs, ys, zs, -0.5, 0.5, 1, 1, 1.0, 1, 0, min_neighbours=1, max_neighbours=1)
    assert one[0, 0] == pytest.approx(10.0)
    assert all_n[0, 0] < 10.0
    # the maximum never goes below the minimum
    four = idw_grid(xs, ys, zs, -0.5, 0.5, 1, 1, 1.0, 1, 0, min_neighbours=4, max_neighbours=1)
    assert four[0, 0] < 10.0


def test_select_neighbour_distances_rule():
    from agriprecisa.core.idw_math import select_neighbour_distances
    d = np.array([1.0, 2.0, 3.0, 10.0, 20.0, 30.0])
    assert select_neighbour_distances(d, 5.0, 4, 16).tolist() == [1, 2, 3, 10]   # minimum
    assert select_neighbour_distances(d, 25.0, 2, 3).tolist() == [1, 2, 3]       # maximum
    assert select_neighbour_distances(d, 25.0, 2, 0).tolist() == [1, 2, 3, 10, 20]
    assert select_neighbour_distances(d, 0, 2, 0).size == 6                       # no radius


def test_share_beyond_radius_and_knn():
    from agriprecisa.core.idw_math import nearest_k_distances, share_beyond_radius
    xs, ys = np.array([0.0, 10.0, 20.0]), np.zeros(3)
    knn = nearest_k_distances([0.0, 20.0], [0.0, 0.0], xs, ys, 4)
    assert knn.shape == (2, 4) and knn[0, :3].tolist() == [0, 10, 20] and np.isinf(knn[0, 3])
    assert share_beyond_radius(knn, 2, 10.0) == 0.0
    assert share_beyond_radius(knn, 3, 10.0) == 100.0


def test_radius_from_knn_reaches_minimum_everywhere():
    from agriprecisa.core.idw_math import radius_from_knn
    knn = np.array([[1.0, 2.0, 3.0, 4.0], [1.0, 2.0, 3.0, 50.0]] + [[1.0, 2.0, 3.0, 4.0]] * 18)
    # max 3 in 95 % -> 3 m, but the minimum of 4 reaches 50 m in one pixel
    assert radius_from_knn(knn, 3, 4) == 50.0
    assert radius_from_knn(knn, 3, 2) == 3.0
    assert radius_from_knn(knn, 3, 2, coverage=7.2) == 8.0
