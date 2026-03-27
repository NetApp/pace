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
