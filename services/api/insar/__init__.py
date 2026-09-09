"""InSAR deformation data serving.

This module provides deformation time series data from Sentinel-1 SBAS
interferometry. The data is pre-computed offline and served through
a live-looking API.

See docs/TRD.md §5 for the full specification.
"""

from __future__ import annotations
