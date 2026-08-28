import numpy as np

from risk.model import feature_importance, predict, train


def _synthetic_dataset(n=200, seed=0):
    rng = np.random.default_rng(seed)
    hand = rng.uniform(0, 30, n)
    rain_72h = rng.uniform(0, 150, n)
    slope = rng.uniform(0, 40, n)
    # a real predictive signal: flooded where HAND is low and rainfall is high -
    # the model should learn this, not just memorize noise
    labels = ((hand < 5) & (rain_72h > 60)).astype(int)
    features = np.column_stack([hand, rain_72h, slope])
    return features, labels, ["hand_m", "rain_72h", "slope_deg"]


def test_predict_returns_higher_risk_for_low_hand_high_rain():
    features, labels, names = _synthetic_dataset()
    booster = train(features, labels, feature_names=names)

    flood_like = np.array([[2.0, 100.0, 3.0]])   # low hand, high rain -> should predict flooded
    safe_like = np.array([[25.0, 5.0, 3.0]])      # high hand, low rain -> should predict dry

    flood_score = predict(booster, flood_like)[0]
    safe_score = predict(booster, safe_like)[0]

    assert flood_score > safe_score


def test_predict_returns_scores_in_zero_one():
    features, labels, names = _synthetic_dataset()
    booster = train(features, labels, feature_names=names)

    scores = predict(booster, features)

    assert np.all(scores >= 0.0)
    assert np.all(scores <= 1.0)


def test_feature_importance_ranks_hand_and_rain_above_slope():
    # slope carries no signal in the synthetic labels - the model
    # should learn to rely on hand/rain_72h far more than slope
    features, labels, names = _synthetic_dataset()
    booster = train(features, labels, feature_names=names)

    importance = feature_importance(booster)

    assert set(importance.keys()) == {"hand_m", "rain_72h", "slope_deg"}
    assert importance["hand_m"] + importance["rain_72h"] > importance["slope_deg"]
