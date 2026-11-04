# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Shared smoke acceptance configuration; not scientific protocol verification."""
from __future__ import annotations

from collections.abc import Mapping

from .statistics import _real


def resolve_acceptance(config):
    """Resolve legacy top-level or nested acceptance thresholds without mutation."""
    if not isinstance(config, Mapping):
        raise ValueError("config must be a mapping")
    nested = config.get("acceptance", {})
    if not isinstance(nested, Mapping):
        raise ValueError("acceptance must be a mapping")
    defaults = {"primary_rms_threshold": 0.01, "min_success_fraction": 0.9}
    unknown = set(nested) - set(defaults)
    if unknown:
        raise ValueError(f"unknown acceptance fields: {sorted(unknown)}")
    resolved = {}
    for name, default in defaults.items():
        candidates = [source[name] for source in (config, nested) if name in source]
        values = [_real(value, name) for value in candidates]
        if any(value < 0 or (name == "min_success_fraction" and value > 1) for value in values):
            raise ValueError(f"{name} is outside its valid range")
        if len(values) == 2 and values[0] != values[1]:
            raise ValueError(f"conflicting acceptance values for {name}")
        resolved[name] = values[0] if values else default
    return resolved
