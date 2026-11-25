"""DTM and plant height in row crops: pure math (core/mdt_math.py), no QGIS."""
import numpy as np
import pytest

from agriprecisa.core import mdt_math as mm

PIXEL = 0.25


def synthetic_field(spacing=3.6, crown=1.6, height=2.0, slope=0.05, n=240, pixel=PIXEL):
    """Sloped terrain (5 percent) with gentle waves and coffee-like rows of crowns."""
    y, x = np.mgrid[0:n, 0:n] * pixel
    terrain = 600 + slope * x + 0.3 * np.sin(y / 15.0)
    in_row = (np.mod(x, spacing) < crown)
    dsm = terrain + np.where(in_row, height, 0.0)
    return dsm, terrain, in_row


def test_dtm_recovers_terrain_and_plant_height():
    dsm, terrain, in_row = synthetic_field()
    window = mm.window_pixels(3.6, 1.5, PIXEL)
    dtm, height, soil = mm.dtm_from_dsm(dsm, window, 0.25)
    core = (slice(30, -30), slice(30, -30))                 # away from the borders
    assert np.nanmax(np.abs(dtm - terrain)[core]) < 0.15
    assert np.nanmedian(height[core][in_row[core]]) == pytest.approx(2.0, abs=0.15)
    assert np.nanmedian(height[core][~in_row[core]]) == pytest.approx(0.0, abs=0.1)
    # soil classification matches the inter-rows
    assert (soil[core] == ~in_row[core]).mean() > 0.9
    stats = mm.height_stats(height, soil, np.isfinite(dsm))
    assert stats["mean"] == pytest.approx(2.0, abs=0.2)


def test_dtm_never_above_dsm_and_nan_outside_data():
    dsm, _, _ = synthetic_field(n=120)
    dsm[:10, :] = np.nan
    dtm, height, soil = mm.dtm_from_dsm(dsm, 23, 0.25)
    assert np.all(np.isnan(dtm[:10, :]))
    assert not soil[:10, :].any()
    assert np.nanmin(height) >= -1e-9


def test_narrow_rows_with_soybean_preset():
    spacing, res, tol = mm.resolve_parameters(3, 0, 0, 0)
    dsm, terrain, in_row = synthetic_field(spacing=spacing, crown=0.25, height=0.6, slope=0.02,
                                           n=300, pixel=res)
    window = mm.window_pixels(spacing, mm.DEFAULT_FACTOR, res)
    assert window >= mm.MIN_WINDOW
    dtm, height, soil = mm.dtm_from_dsm(dsm, window, tol)
    core = (slice(20, -20), slice(20, -20))
    assert np.nanmax(np.abs(dtm - terrain)[core]) < 0.08
    assert np.nanmedian(height[core][in_row[core]]) == pytest.approx(0.6, abs=0.08)


@pytest.mark.parametrize("crop,expected", [
    (0, (3.6, 0.25, 0.25)),            # coffee
    (3, (0.5, 0.10, 0.10)),            # soybean
])
def test_crop_values_used_when_fields_are_zero(crop, expected):
    assert mm.resolve_parameters(crop, 0, 0, 0) == expected


def test_user_values_override_crop():
    assert mm.resolve_parameters(0, 4.0, 0.2, 0.3) == (4.0, 0.2, 0.3)
    assert mm.resolve_parameters(0, 4.0, 0, 0) == (4.0, 0.25, 0.25)


def test_custom_crop_needs_spacing_and_derives_resolution():
    assert mm.resolve_parameters(mm.CUSTOM, 0, 0, 0)[0] is None
    spacing, res, tol = mm.resolve_parameters(mm.CUSTOM, 0.6, 0, 0)
    assert (spacing, res, tol) == (0.6, 0.15, mm.DEFAULT_TOLERANCE)
    assert res <= mm.recommended_resolution(spacing)


def test_every_preset_keeps_four_pixels_and_a_valid_window():
    for key, spacing, res, tol in mm.CROPS[:-1]:
        assert res <= mm.recommended_resolution(spacing) + 1e-9, key
        assert mm.window_pixels(spacing, mm.DEFAULT_FACTOR, res) >= mm.MIN_WINDOW, key
        assert tol < 0.5, key


def test_window_is_odd():
    for spacing in (0.5, 0.8, 1.5, 3.6, 6.5):
        assert mm.window_pixels(spacing, 1.5, 0.25) % 2 == 1


def test_soil_percent_and_fill_nearest():
    soil = np.array([[True, False], [False, False]])
    valid = np.array([[True, True], [True, False]])
    assert mm.soil_percent(soil, valid) == pytest.approx(100 / 3)
    filled = mm.fill_nearest(np.array([[1.0, np.nan], [np.nan, 4.0]]))
    assert not np.isnan(filled).any()


def test_crop_field_values_for_the_dialog():
    """Regression 2.0.1: choosing a crop must show its values in the dialog fields."""
    assert mm.crop_field_values(0) == {"SPACING": 3.6, "RESOLUTION": 0.25, "TOLERANCE": 0.25}
    assert mm.crop_field_values(3)["SPACING"] == 0.5
    assert mm.crop_field_values(mm.CUSTOM) == {}
    assert mm.crop_field_values(None) == {}
    assert mm.crop_field_values(99) == {}
