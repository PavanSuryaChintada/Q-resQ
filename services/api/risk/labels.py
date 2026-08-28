"""Sentinel-1 SAR flood extent -> binary flood mask for training
risk/model.py. See BUILD_SPEC.md and docs/TRD.md #3.

Smooth water gives low backscatter (specular reflection away from the
sensor). Threshold, then morphological opening to drop speckle -
sensor noise produces isolated below-threshold pixels that aren't
real water bodies.
"""

from __future__ import annotations

import numpy as np
from scipy.ndimage import binary_opening


def flood_mask(backscatter_db: np.ndarray, threshold_db: float = -18.0) -> np.ndarray:
    raw_mask = backscatter_db < threshold_db
    return binary_opening(raw_mask, structure=np.ones((3, 3)))
