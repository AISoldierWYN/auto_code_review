"""Demo module for Stage 1 — loads a key=value cache file from disk.

This file represents the **after** state of the demo diff. It contains a
deliberate resource-leak bug (file opened without ``with``) that the
``RULE-RESOURCE-001`` review rule is designed to catch.
"""

from __future__ import annotations


def load_cache(path: str) -> dict[str, str]:
    f = open(path, "r", encoding="utf-8")
    data: dict[str, str] = {}
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip()
    return data
