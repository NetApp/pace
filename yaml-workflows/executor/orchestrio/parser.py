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

"""Load and validate workflow definitions from YAML / JSON files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from orchestrio.models import IncludeRecord, WorkflowDefinition
from orchestrio.utils import deep_merge

logger = logging.getLogger("orchestrio.parser")


class IncludeError(Exception):
    """Raised when a step ``include`` reference cannot be resolved."""


# ── Public API ─────────────────────────────────────────────────────


def load_workflow(
    source: str | Path | dict[str, Any],
    *,
    base_dir: Path | None = None,
) -> WorkflowDefinition:
    """Load a workflow from a file path, raw string, or dict.

    Args:
        source: Path to a YAML/JSON file, a raw YAML/JSON string, or a dict.
        base_dir: Directory used to resolve ``include`` paths when *source* is
                  a dict or raw string.  Ignored when *source* is a file path
                  (the file's parent is used instead).

    Returns:
        A validated WorkflowDefinition.
    """
    if isinstance(source, dict):
        meta = _resolve_includes(source, base_dir or Path.cwd())
        wf = WorkflowDefinition(**source)
        wf.include_meta = meta
        return wf

    path = Path(source)
    if path.is_file():
        return _load_from_file(path)

    # Treat as a raw YAML/JSON string
    return _load_from_string(str(source), base_dir or Path.cwd())


# ── File / string loaders ─────────────────────────────────────────


def _load_from_file(path: Path) -> WorkflowDefinition:
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif path.suffix == ".json":
        data = json.loads(text)
    else:
        # Try YAML first — it is a superset of JSON
        data = yaml.safe_load(text)
    meta = _resolve_includes(data, path.parent)
    wf = WorkflowDefinition(**data)
    wf.include_meta = meta
    return wf


def _load_from_string(raw: str, base_dir: Path) -> WorkflowDefinition:
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        data = json.loads(raw)
    meta = _resolve_includes(data, base_dir)
    wf = WorkflowDefinition(**data)
    wf.include_meta = meta
    return wf


# ── Include resolution ─────────────────────────────────────────────


def _resolve_includes(data: dict[str, Any], base_dir: Path) -> list[IncludeRecord]:
    """Resolve ``include`` entries in the steps list **in-place**.

    Each include entry is replaced with the fully-merged step dict so
    that downstream code (Pydantic model, engine) only ever sees normal
    step definitions.

    Returns a list of :class:`IncludeRecord` describing each resolved include.
    """
    steps: list[dict[str, Any]] | None = data.get("steps")
    if not steps:
        return []

    records: list[IncludeRecord] = []
    for idx, entry in enumerate(steps):
        include_path = entry.get("include")
        if include_path is None:
            continue

        fragment = _load_fragment(include_path, base_dir, step_index=idx)
        override = entry.get("override", {})

        merged = _merge_fragment(fragment, override)
        steps[idx] = merged

        records.append(
            IncludeRecord(
                step_index=idx,
                step_name=merged.get("name", "?"),
                include_path=include_path,
            )
        )
        logger.debug(
            "Step %d: included '%s' (resolved name='%s')",
            idx,
            include_path,
            merged.get("name", "?"),
        )

    return records


def _load_fragment(include_path: str, base_dir: Path, *, step_index: int) -> dict[str, Any]:
    """Load a step fragment YAML file, searching relative to *base_dir*."""
    candidate = base_dir / include_path
    if not candidate.is_file():
        raise IncludeError(
            f"Step {step_index}: include file '{include_path}' not found. Searched: {candidate}"
        )

    text = candidate.read_text()
    try:
        fragment = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise IncludeError(
            f"Step {step_index}: include file '{include_path}' contains invalid YAML: {exc}"
        ) from exc

    if not isinstance(fragment, dict):
        raise IncludeError(
            f"Step {step_index}: include file '{include_path}' must be a YAML mapping, "
            f"got {type(fragment).__name__}"
        )

    if "name" not in fragment or "type" not in fragment:
        raise IncludeError(
            f"Step {step_index}: include file '{include_path}' must define 'name' and 'type'"
        )

    return fragment


def _merge_fragment(fragment: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override values on top of a loaded fragment.

    ``config`` is deep-merged (override wins at leaf level).
    All other keys are replaced outright.
    """
    if not override:
        return dict(fragment)

    merged = dict(fragment)

    config_override = override.get("config")
    if config_override and isinstance(merged.get("config"), dict):
        merged["config"] = deep_merge(merged["config"], config_override)

    for key, val in override.items():
        if key == "config":
            continue
        merged[key] = val

    return merged
