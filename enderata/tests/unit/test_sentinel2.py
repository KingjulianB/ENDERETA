from enderata.satellite.sentinel2 import _compute_out_shape

# The real Luanda municipality boundary's bounds (aoi.py::load_luanda_aoi(),
# verified 2026-09-22 -- literal here rather than calling it live, since
# that needs network/Overpass and this module's own logic is pure).
LUANDA_BOUNDS = (13.1732251, -8.9208267, 13.3108619, -8.759227)


def test_out_shape_matches_square_bbox_target_resolution():
    # ~1km square at the equator -> ~100 pixels at 10m/pixel
    west, south = 0.0, 0.0
    east, north = 0.009, 0.009  # ~1km at the equator
    height_px, width_px = _compute_out_shape((west, south, east, north), target_resolution_m=10.0)
    assert 90 <= height_px <= 110
    assert 90 <= width_px <= 110


def test_out_shape_preserves_real_aspect_ratio_for_a_non_square_bbox():
    west, south, east, north = LUANDA_BOUNDS
    height_px, width_px = _compute_out_shape((west, south, east, north))
    # real bbox is taller (N-S) than wide (E-W) -- height/width should
    # reflect that, not be forced to 1:1 like the old out_size=out_size did
    assert height_px > width_px
    assert 1.1 < height_px / width_px < 1.3  # ~18km / ~15.1km ~= 1.19


def test_out_shape_respects_max_dimension_cap_while_preserving_aspect_ratio():
    west, south, east, north = LUANDA_BOUNDS
    uncapped_h, uncapped_w = _compute_out_shape((west, south, east, north), max_dimension=100_000)
    capped_h, capped_w = _compute_out_shape((west, south, east, north), max_dimension=500)

    assert max(capped_h, capped_w) <= 500
    # aspect ratio preserved within rounding
    assert abs((uncapped_h / uncapped_w) - (capped_h / capped_w)) < 0.01


def test_out_shape_is_always_at_least_one_pixel_per_side():
    height_px, width_px = _compute_out_shape((0.0, 0.0, 0.0001, 0.0001))
    assert height_px >= 1
    assert width_px >= 1
