import numpy as np
import pytest

from risk.heuristic import band, compute_heuristic_risk


def test_steeper_slope_scores_higher_than_gentler_slope():
    # two cells, identical on every other term - only slope differs
    slope_deg = np.array([2.0, 35.0])
    curv_prof = np.array([0.0, 0.0])
    is_cut_slope = np.array([0.0, 0.0])
    forest_frac = np.array([0.5, 0.5])
    ls_factor = np.array([1.0, 1.0])

    risk, _ = compute_heuristic_risk(slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor)

    assert risk[1] > risk[0]


def test_cut_slope_flag_scores_higher_than_an_otherwise_identical_cell():
    slope_deg = np.array([20.0, 20.0])
    curv_prof = np.array([0.0, 0.0])
    is_cut_slope = np.array([0.0, 1.0])
    forest_frac = np.array([0.5, 0.5])
    ls_factor = np.array([1.0, 1.0])

    risk, _ = compute_heuristic_risk(slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor)

    assert risk[1] > risk[0]


def test_risk_score_is_bounded_zero_to_one():
    rng = np.random.default_rng(0)
    n = 50
    slope_deg = rng.uniform(0, 45, n)
    curv_prof = rng.uniform(-5, 5, n)
    is_cut_slope = rng.integers(0, 2, n).astype(float)
    forest_frac = rng.uniform(0, 1, n)
    ls_factor = rng.uniform(0, 10, n)

    risk, _ = compute_heuristic_risk(slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor)

    assert np.all(risk >= -1e-9)
    assert np.all(risk <= 1.0 + 1e-9)


def test_returns_per_term_contributions_matching_the_documented_weights_without_lithology():
    slope_deg = np.array([1.0, 5.0, 20.0])
    curv_prof = np.array([-2.0, 0.0, 2.0])
    is_cut_slope = np.array([0.0, 1.0, 1.0])
    forest_frac = np.array([0.9, 0.5, 0.1])
    ls_factor = np.array([0.5, 2.0, 8.0])

    risk, contributions = compute_heuristic_risk(slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor)

    assert set(contributions.keys()) == {"slope", "curv_prof", "is_cut_slope", "forest_frac", "ls_factor"}
    # contributions sum back to the total risk score
    total = sum(contributions.values())
    assert np.allclose(total, risk)


def test_missing_lithology_renormalises_weights_to_sum_to_one():
    # a cell scoring the max on every non-lithology term should hit a
    # risk score of 1.0, not 0.85 - if lithology's 0.15 weight silently
    # vanished instead of being redistributed, every score would be
    # depressed and the IMD band thresholds would shift underneath the map
    n = 100
    slope_deg = np.linspace(0, 45, n)          # last = steepest
    curv_prof = np.linspace(5, -5, n)          # last = most concave (-curv_prof term wants this high)
    is_cut_slope = np.ones(n)                  # constant - not percentile-normalised
    forest_frac = np.linspace(1, 0, n)         # last = least forest
    ls_factor = np.linspace(0, 10, n)          # last = highest

    risk, contributions = compute_heuristic_risk(slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor)

    assert "lithology" not in contributions
    assert np.isclose(risk[-1], 1.0, atol=1e-6)  # top of every remaining term


def test_lithology_weight_is_included_and_normalised_when_available():
    slope_deg = np.array([1.0, 5.0, 20.0])
    curv_prof = np.array([-2.0, 0.0, 2.0])
    is_cut_slope = np.array([0.0, 1.0, 1.0])
    forest_frac = np.array([0.9, 0.5, 0.1])
    ls_factor = np.array([0.5, 2.0, 8.0])
    lithology_weight = np.array([0.1, 0.5, 0.9])

    risk, contributions = compute_heuristic_risk(
        slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor, lithology_weight=lithology_weight,
    )

    assert set(contributions.keys()) == {
        "slope", "curv_prof", "is_cut_slope", "forest_frac", "ls_factor", "lithology",
    }
    total = sum(contributions.values())
    assert np.allclose(total, risk)
    # unrenormalised weights (0.30+0.20+0.20+0.15+0.10+0.05) should still sum to 1.0
    assert np.all(risk <= 1.0 + 1e-9)


def test_constant_field_does_not_produce_nan():
    # every cell identical on a term - min-max norm has a zero range
    slope_deg = np.full(5, 20.0)
    curv_prof = np.full(5, 0.0)
    is_cut_slope = np.full(5, 0.0)
    forest_frac = np.full(5, 0.5)
    ls_factor = np.full(5, 2.0)

    risk, contributions = compute_heuristic_risk(slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor)

    assert not np.any(np.isnan(risk))
    for values in contributions.values():
        assert not np.any(np.isnan(values))


def test_a_few_extreme_outliers_do_not_flatten_the_rest_of_the_map():
    # 100 cells clustered in a realistic moderate-slope range, plus 3
    # near-vertical outliers. Plain min-max normalisation would
    # compress all 100 clustered cells toward the same near-maximum
    # risk value (exactly what made the old flood-build risk map render
    # as a near-uniform wash of one colour) - percentile-based
    # normalising should keep meaningful spread within the majority.
    rng = np.random.default_rng(1)
    clustered = rng.uniform(5.0, 25.0, 100)
    outliers = np.array([70.0, 80.0, 89.0])
    slope_deg = np.concatenate([clustered, outliers])
    curv_prof = np.zeros(len(slope_deg))
    is_cut_slope = np.zeros(len(slope_deg))
    forest_frac = np.full(len(slope_deg), 0.5)
    ls_factor = np.full(len(slope_deg), 2.0)

    risk, contributions = compute_heuristic_risk(slope_deg, curv_prof, is_cut_slope, forest_frac, ls_factor)

    slope_contribution_clustered = contributions["slope"][:100]
    # with real spread preserved, the clustered majority should not
    # all collapse into a tiny band near the same value
    assert slope_contribution_clustered.max() - slope_contribution_clustered.min() > 0.15


@pytest.mark.parametrize("score,expected_band", [
    (0.0, 0), (0.19, 0),
    (0.2, 1), (0.39, 1),
    (0.4, 2), (0.59, 2),
    (0.6, 3), (0.79, 3),
    (0.8, 4), (1.0, 4),
])
def test_band_thresholds_match_the_imd_ladder(score, expected_band):
    assert band(score) == expected_band
