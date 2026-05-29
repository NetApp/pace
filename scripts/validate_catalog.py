#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Validate catalog.yaml against repo examples.

Checks structural fields, path existence, and bidirectional coverage between
catalog entries and python/, ansible/, and terraform/ artifacts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "error: PyYAML is required — install with: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "catalog.yaml"

VALID_STATUS = frozenset({"draft", "verified", "deprecated"})
VALID_TOOLS = frozenset({"python", "ansible", "terraform"})
KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

USE_CASE_REQUIRED = ("id", "description", "products", "ontap_min", "status", "variants")
VARIANT_REQUIRED = ("path", "command", "cwd", "prerequisites", "inputs", "outputs")
PREREQ_REQUIRED = ("setup", "env")


def _err(errors: list[str], message: str) -> None:
    errors.append(message)


def _discover_python() -> set[str]:
    return {
        str(p.relative_to(ROOT))
        for p in (ROOT / "python").glob("*.py")
        if p.name != "ontap_client.py"
    }


def _discover_ansible() -> set[str]:
    return {
        str(p.relative_to(ROOT))
        for p in (ROOT / "ansible").glob("*.yml")
        if p.name != "requirements.yml"
    }


def _discover_terraform() -> set[str]:
    return {str(p.relative_to(ROOT)) for p in (ROOT / "terraform").iterdir() if p.is_dir()}


def validate_catalog(data: object) -> list[str]:
    errors: list[str] = []
    catalog_paths: set[str] = set()

    if not isinstance(data, dict):
        _err(errors, "catalog root must be a mapping")
        return errors

    use_cases = data.get("use_cases")
    if not isinstance(use_cases, list) or not use_cases:
        _err(errors, "'use_cases' must be a non-empty list")
        return errors

    seen_ids: set[str] = set()

    for index, use_case in enumerate(use_cases):
        prefix = f"use_cases[{index}]"
        if not isinstance(use_case, dict):
            _err(errors, f"{prefix}: must be a mapping")
            continue

        for field in USE_CASE_REQUIRED:
            if field not in use_case:
                _err(errors, f"{prefix}: missing required field '{field}'")

        use_id = use_case.get("id", "")
        if not isinstance(use_id, str) or not KEBAB_CASE.match(use_id):
            _err(errors, f"{prefix}: 'id' must be kebab-case")
        elif use_id in seen_ids:
            _err(errors, f"{prefix}: duplicate id '{use_id}'")
        else:
            seen_ids.add(use_id)

        status = use_case.get("status")
        if status not in VALID_STATUS:
            _err(errors, f"{prefix}: 'status' must be one of {sorted(VALID_STATUS)}")

        description = use_case.get("description")
        if not isinstance(description, str) or not description.strip():
            _err(errors, f"{prefix}: 'description' must be a non-empty string")

        products = use_case.get("products")
        if not isinstance(products, list) or not products:
            _err(errors, f"{prefix}: 'products' must be a non-empty list")

        ontap_min = use_case.get("ontap_min")
        if not isinstance(ontap_min, str) or not ontap_min.strip():
            _err(errors, f"{prefix}: 'ontap_min' must be a non-empty string")

        variants = use_case.get("variants")
        if not isinstance(variants, dict) or not variants:
            _err(errors, f"{prefix}: 'variants' must be a non-empty mapping")
            continue

        for tool, variant in variants.items():
            vprefix = f"{prefix}.variants.{tool}"
            if tool not in VALID_TOOLS:
                _err(errors, f"{vprefix}: unknown tool (expected python, ansible, terraform)")
                continue
            if not isinstance(variant, dict):
                _err(errors, f"{vprefix}: must be a mapping")
                continue

            for field in VARIANT_REQUIRED:
                if field not in variant:
                    _err(errors, f"{vprefix}: missing required field '{field}'")

            path = variant.get("path")
            if not isinstance(path, str) or not path.strip():
                _err(errors, f"{vprefix}: 'path' must be a non-empty string")
            else:
                catalog_paths.add(path)
                full_path = ROOT / path
                if not full_path.exists():
                    _err(errors, f"{vprefix}: path does not exist: {path}")

            for field in ("command", "cwd"):
                value = variant.get(field)
                if not isinstance(value, str) or not value.strip():
                    _err(errors, f"{vprefix}: '{field}' must be a non-empty string")

            prerequisites = variant.get("prerequisites")
            if not isinstance(prerequisites, dict):
                _err(errors, f"{vprefix}: 'prerequisites' must be a mapping")
            else:
                for field in PREREQ_REQUIRED:
                    if field not in prerequisites:
                        _err(errors, f"{vprefix}.prerequisites: missing '{field}'")
                setup = prerequisites.get("setup")
                if not isinstance(setup, str) or not setup.strip():
                    _err(errors, f"{vprefix}.prerequisites.setup must be a non-empty string")
                env = prerequisites.get("env")
                if not isinstance(env, list):
                    _err(errors, f"{vprefix}.prerequisites.env must be a list")

            for field in ("inputs", "outputs"):
                value = variant.get(field)
                if not isinstance(value, list):
                    _err(errors, f"{vprefix}: '{field}' must be a list")

    _check_coverage(errors, catalog_paths)
    return errors


def _check_coverage(errors: list[str], catalog_paths: set[str]) -> None:
    expected = _discover_python() | _discover_ansible() | _discover_terraform()

    for path in sorted(expected - catalog_paths):
        _err(errors, f"uncataloged example: {path} (add to catalog.yaml)")

    for path in sorted(catalog_paths - expected):
        _err(errors, f"catalog path has no matching repo artifact: {path}")


def main() -> int:
    if not CATALOG_PATH.is_file():
        print(f"error: missing {CATALOG_PATH.relative_to(ROOT)}", file=sys.stderr)
        return 1

    with CATALOG_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    errors = validate_catalog(data)
    if errors:
        print(f"catalog validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        return 1

    use_cases = data["use_cases"]
    variant_count = sum(len(uc["variants"]) for uc in use_cases)
    print(
        f"catalog OK — {len(use_cases)} use case(s), {variant_count} variant(s), "
        f"{len(_discover_python())} python, "
        f"{len(_discover_ansible())} ansible, "
        f"{len(_discover_terraform())} terraform"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
