# Copyright (C) 2026 Jean-François Brisson
# SPDX-License-Identifier: AGPL-3.0-only
"""Content-addressed provenance for checkouts and installed distributions."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from importlib import metadata
from pathlib import Path

import numpy as np


def canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def source_hashes():
    package = Path(__file__).resolve().parent
    hashes = {
        str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package.rglob("*"))
        if path.is_file() and path.suffix in {".py", ".json"}
    }
    if "benchmark.py" not in hashes or "provenance.py" not in hashes:
        raise RuntimeError("incomplete package provenance inventory")
    return hashes


def provenance():
    hashes = source_hashes()
    try:
        package_version = metadata.version("waveholo-telescope")
        distribution = metadata.distribution("waveholo-telescope")
        record = distribution.read_text("RECORD")
    except metadata.PackageNotFoundError:
        from . import __version__
        package_version, record = __version__, None
    environment = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "numpy_version": np.__version__,
    }
    result = {
        "package_version": package_version,
        "source_hashes": hashes,
        "source_inventory_status": "complete",
        "package_content_sha256": canonical_hash(hashes),
        "installed_record_sha256": (
            hashlib.sha256(record.encode("utf-8")).hexdigest() if record else None
        ),
        "environment": environment,
        "environment_sha256": canonical_hash(environment),
    }
    root = Path(__file__).resolve().parents[2]
    if (root / ".git").exists():
        result["checkout_commit"] = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        result["checkout_dirty"] = bool(subprocess.check_output(
            ["git", "-C", str(root), "status", "--porcelain"], text=True
        ).strip())
    return result
