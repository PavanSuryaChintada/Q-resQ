"""LightGBM risk model, trained on Sentinel-1 SAR flood labels
(risk/labels.py). See BUILD_SPEC.md and docs/TRD.md #3.

Not deep learning: faster to train, better on tabular terrain/rainfall
features, and it yields feature importances - the map detail panel
needs the top three contributors per cell, same contract as the
heuristic path in risk/heuristic.py.
"""

from __future__ import annotations

import lightgbm as lgb
import numpy as np


def train(features: np.ndarray, labels: np.ndarray, feature_names: list[str],
          num_boost_round: int = 100) -> lgb.Booster:
    dataset = lgb.Dataset(features, label=labels, feature_name=feature_names)
    params = {"objective": "binary", "metric": "auc", "verbosity": -1}
    return lgb.train(params, dataset, num_boost_round=num_boost_round)


def predict(booster: lgb.Booster, features: np.ndarray) -> np.ndarray:
    return booster.predict(features)


def feature_importance(booster: lgb.Booster) -> dict[str, float]:
    names = booster.feature_name()
    gains = booster.feature_importance(importance_type="gain")
    total = float(gains.sum())
    if total <= 0:
        return {name: 0.0 for name in names}
    return {name: float(gain) / total for name, gain in zip(names, gains)}
