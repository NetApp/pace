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

"""Load environment variables from external files (.env, .yaml, .json)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("orchestrio.env")


class EnvLoadError(Exception):
    """Raised when an env file cannot be loaded or parsed."""


def load_env_file(path: Path) -> dict[str, str]:
    """Load a flat key-value env dict from a file.

    Supported formats:
        - ``.env`` / no extension — ``KEY=VALUE`` lines (shell-style)
        - ``.yaml`` / ``.yml`` — flat mapping
        - ``.json`` — flat JSON object

    Returns:
        A ``dict[str, str]`` of environment variable names to values.

    Raises:
        EnvLoadError: If the file cannot be read or parsed.
    """
    if not path.is_file():
        raise EnvLoadError(f"Env file not found: {path}")

    try:
        text = path.read_text()
    except OSError as exc:
        raise EnvLoadError(f"Cannot read env file {path}: {exc}") from exc

    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        return _parse_yaml(text, path)
    if suffix == ".json":
        return _parse_json(text, path)
    return _parse_dotenv(text, path)


def parse_env_pairs(pairs: tuple[str, ...]) -> dict[str, str]:
    """Parse ``KEY=VALUE`` strings from ``--env`` CLI flags.

    Raises:
        EnvLoadError: If any pair is malformed.
    """
    result: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise EnvLoadError(f"Invalid --env value '{pair}': expected KEY=VALUE format")
        key, _, value = pair.partition("=")
        key = key.strip()
        if not key:
            raise EnvLoadError(f"Invalid --env value '{pair}': empty key")
        result[key] = value
    return result


def merge_env(
    yaml_env: dict[str, str],
    env_file_vars: dict[str, str],
    cli_env_vars: dict[str, str],
) -> dict[str, str]:
    """Merge env sources with a clear precedence chain.

    Priority (highest wins):
        1. ``cli_env_vars``   — ``--env KEY=VALUE`` inline overrides
        2. ``env_file_vars``  — ``--env-file`` values
        3. ``os.environ``     — only for keys declared in ``yaml_env``
        4. ``yaml_env``       — YAML ``env:`` block defaults

    The ``os.environ`` lookup is **scoped**: only keys that appear in
    ``yaml_env`` are looked up, preventing leakage of arbitrary system vars.
    """
    merged = dict(yaml_env)

    for key in yaml_env:
        os_val = os.environ.get(key)
        if os_val is not None:
            merged[key] = os_val

    merged.update(env_file_vars)
    merged.update(cli_env_vars)
    return merged


# ── Private parsers ────────────────────────────────────────────────


def _parse_dotenv(text: str, path: Path) -> dict[str, str]:
    """Parse a shell-style .env file (KEY=VALUE per line)."""
    result: dict[str, str] = {}
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise EnvLoadError(f"{path}:{lineno}: expected KEY=VALUE, got: {raw_line!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value and value[0] in ('"', "'") and value[-1] == value[0] and len(value) >= 2:
            value = value[1:-1]
        result[key] = value
    return result


def _parse_yaml(text: str, path: Path) -> dict[str, str]:
    """Parse a YAML file expecting a flat string mapping."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EnvLoadError(f"Invalid YAML in {path}: {exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise EnvLoadError(f"{path}: expected a flat key-value mapping, got {type(data).__name__}")
    return _coerce_flat_dict(data, path)


def _parse_json(text: str, path: Path) -> dict[str, str]:
    """Parse a JSON file expecting a flat string object."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise EnvLoadError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise EnvLoadError(f"{path}: expected a flat key-value object, got {type(data).__name__}")
    return _coerce_flat_dict(data, path)


def _coerce_flat_dict(data: dict[str, Any], path: Path) -> dict[str, str]:
    """Ensure all values are scalars and coerce to str."""
    result: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            raise EnvLoadError(f"{path}: nested values are not allowed (key '{key}')")
        result[str(key)] = str(value) if value is not None else ""
    return result
