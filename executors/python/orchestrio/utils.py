# Copyright 2026 NetApp, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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
