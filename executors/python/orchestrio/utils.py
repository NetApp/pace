"""Shared utilities used across the Orchestrio engine and plugins."""

from __future__ import annotations

from typing import Any


def walk_path(obj: Any, dotted_path: str) -> Any:
    """Traverse a dotted path through nested dicts and lists.

    Supports both dict keys and integer list indices, e.g.
    ``records.0.cluster_interfaces.0.ip.address``.

    Returns ``None`` when a segment cannot be resolved.
    """
    for key in dotted_path.strip(".").split("."):
        if isinstance(obj, dict):
            obj = obj.get(key)
        elif isinstance(obj, list):
            try:
                obj = obj[int(key)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return obj
