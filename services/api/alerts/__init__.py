"""Alerts module - CAP (Common Alerting Protocol) generation.

This module generates CAP-compliant alert payloads for landslide warnings.
Alerts are geo-fenced and evaluated on-device for offline capability.

See schema.sql for the database schema.
"""

from __future__ import annotations
