"""Load and validate workflow definitions from YAML / JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from orchestrio.models import WorkflowDefinition


def load_workflow(source: str | Path | dict[str, Any]) -> WorkflowDefinition:
    """Load a workflow from a file path, raw string, or dict.

    Args:
        source: Path to a YAML/JSON file, a raw YAML/JSON string, or a dict.

    Returns:
        A validated WorkflowDefinition.
    """
    if isinstance(source, dict):
        return WorkflowDefinition(**source)

    path = Path(source)
    if path.is_file():
        return _load_from_file(path)

    # Treat as a raw YAML/JSON string
    return _load_from_string(str(source))


def _load_from_file(path: Path) -> WorkflowDefinition:
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    elif path.suffix == ".json":
        data = json.loads(text)
    else:
        # Try YAML first — it is a superset of JSON
        data = yaml.safe_load(text)
    return WorkflowDefinition(**data)


def _load_from_string(raw: str) -> WorkflowDefinition:
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        data = json.loads(raw)
    return WorkflowDefinition(**data)
