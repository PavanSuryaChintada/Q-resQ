import numpy as np
import pytest

from risk.heuristic import band, compute_heuristic_risk


def test_lowest_hand_cell_scores_higher_than_highest_hand_cell():
    # two cells, identical on every other term - only HAND differs
    hand = np.array([0.5, 20.0])
    rain_72h = np.array([50.0, 50.0])
    slope_deg = np.array([2.0, 2.0])
    dist_stream_m = np.array([100.0, 100.0])
    drainage_penalty = np.array([0.2, 0.2])

    risk, _ = compute_heuristic_risk(hand, rain_72h, slope_deg, dist_stream_m, drainage_penalty)

    assert risk[0] > risk[1]  # low HAND (near drainage) is riskier


def test_higher_rainfall_scores_higher_risk():
    hand = np.array([5.0, 5.0])
    rain_72h = np.array([120.0, 10.0])
    slope_deg = np.array([3.0, 3.0])
    dist_stream_m = np.array([300.0, 300.0])
    drainage_penalty = np.array([0.1, 0.1])

    risk, _ = compute_heuristic_risk(hand, rain_72h, slope_deg, dist_stream_m, drainage_penalty)

    assert risk[0] > risk[1]


def test_risk_score_is_bounded_zero_to_one():
    rng = np.random.default_rng(0)
    n = 50
    hand = rng.uniform(0, 30, n)
    rain_72h = rng.uniform(0, 150, n)
    slope_deg = rng.uniform(0, 45, n)
    dist_stream_m = rng.uniform(0, 2000, n)
    drainage_penalty = rng.uniform(0, 1, n)

    risk, _ = compute_heuristic_risk(hand, rain_72h, slope_deg, dist_stream_m, drainage_penalty)

    assert np.all(risk >= -1e-9)
    assert np.all(risk <= 1.0 + 1e-9)


def test_returns_per_term_contributions_matching_the_documented_weights():
    hand = np.array([1.0, 10.0, 20.0])
    rain_72h = np.array([10.0, 50.0, 100.0])
    slope_deg = np.array([1.0, 5.0, 20.0])
    dist_stream_m = np.array([50.0, 500.0, 2000.0])
    drainage_penalty = np.array([0.1, 0.5, 0.9])

    risk, contributions = compute_heuristic_risk(hand, rain_72h, slope_deg, dist_stream_m, drainage_penalty)

    assert set(contributions.keys()) == {"hand", "rain_72h", "slope", "dist_stream", "drainage"}
    # contributions sum back to the total risk score
    total = sum(contributions.values())
    assert np.allclose(total, risk)


def test_constant_field_does_not_produce_nan():
    # every cell identical on a term - min-max norm has a zero range
    hand = np.full(5, 10.0)
    rain_72h = np.full(5, 50.0)
    slope_deg = np.full(5, 3.0)
    dist_stream_m = np.full(5, 300.0)
    drainage_penalty = np.full(5, 0.3)

    risk, contributions = compute_heuristic_risk(hand, rain_72h, slope_deg, dist_stream_m, drainage_penalty)

    assert not np.any(np.isnan(risk))
    for values in contributions.values():
        assert not np.any(np.isnan(values))


def test_a_few_extreme_outliers_do_not_flatten_the_rest_of_the_map():
    # 100 cells clustered in a realistic low-lying-floodplain range
    # (0-10m HAND, like most of a real coastal demo area), plus 3
    # hilly outliers up to 140m. Plain min-max normalisation would
    # compress all 100 clustered cells toward the same near-maximum
    # risk value (exactly what made the real risk map render as a
    # near-uniform wash of one colour) - percentile-based normalising
    # should keep meaningful spread within the clustered majority.
    rng = np.random.default_rng(1)
    clustered = rng.uniform(0.0, 10.0, 100)
    outliers = np.array([80.0, 110.0, 140.0])
    hand = np.concatenate([clustered, outliers])
    rain_72h = np.full(len(hand), 50.0)
    slope_deg = np.full(len(hand), 3.0)
    dist_stream_m = np.full(len(hand), 300.0)
    drainage_penalty = np.full(len(hand), 0.3)

    risk, contributions = compute_heuristic_risk(hand, rain_72h, slope_deg, dist_stream_m, drainage_penalty)

    hand_contribution_clustered = contributions["hand"][:100]
    # with real spread preserved, the clustered majority should not
    # all collapse into a tiny band near the same value
    assert hand_contribution_clustered.max() - hand_contribution_clustered.min() > 0.15


@pytest.mark.parametrize("score,expected_band", [
    (0.0, 0), (0.19, 0),
    (0.2, 1), (0.39, 1),
    (0.4, 2), (0.59, 2),
    (0.6, 3), (0.79, 3),
    (0.8, 4), (1.0, 4),
])
def test_band_thresholds_match_the_imd_ladder(score, expected_band):
    assert band(score) == expected_band
