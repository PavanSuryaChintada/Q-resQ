import numpy as np

from risk.labels import flood_mask


def test_low_backscatter_region_is_flagged_as_water():
    # smooth water gives low VV backscatter; land is much higher
    db = np.full((20, 20), -8.0)
    db[5:15, 5:15] = -25.0  # a clear water patch

    mask = flood_mask(db, threshold_db=-18.0)

    assert mask[10, 10] == True  # center of the water patch  # noqa: E712
    assert mask[0, 0] == False  # noqa: E712


def test_isolated_speckle_pixel_is_removed_by_morphological_opening():
    db = np.full((20, 20), -8.0)
    db[10, 10] = -25.0  # a single below-threshold pixel: sensor speckle, not real water

    mask = flood_mask(db, threshold_db=-18.0)

    assert mask[10, 10] == False  # noqa: E712
    assert not mask.any()


def test_a_real_contiguous_water_body_survives_opening():
    db = np.full((20, 20), -8.0)
    db[5:15, 5:15] = -25.0

    mask = flood_mask(db, threshold_db=-18.0)

    assert mask[7:13, 7:13].all()  # the interior of the water patch survives
