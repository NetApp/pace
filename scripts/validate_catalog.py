#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Validate catalog.yaml against repo examples.

Checks structural fields, path existence, product/path agreement, and
bidirectional coverage between catalog entries and the python/, ansible/,
terraform/, and go/ artifacts.

Examples are organized by product — `<tool>/<product>/…`, plus an extra
`/<deployment>/` level for products that have deployment variants. Discovery is
therefore recursive rather than fixed-depth, so a new product folder needs no
change here.
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
VALID_TOOLS = frozenset({"python", "ansible", "terraform", "go"})
VALID_PRODUCTS = frozenset({"ontap", "console"})

# Products whose examples carry an extra deployment level under the product
# folder. A product absent here must not set 'deployment'.
VALID_DEPLOYMENTS: dict[str, frozenset[str]] = {"console": frozenset({"local"})}
VALID_ENVIRONMENT = frozenset(
    {
        "ontap-simulator",
        "ontap-select",
        "real-cluster",
        "cloud-volumes-ontap",
        "other",
    }
)
KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
GITHUB_HANDLE = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

USE_CASE_REQUIRED = (
    "id",
    "description",
    "products",
    "product",
    "ontap_min",
    "owners",
    "status",
    "variants",
)
VARIANT_REQUIRED = ("path", "command", "cwd", "prerequisites", "inputs", "outputs")
PREREQ_REQUIRED = ("setup", "env")
VERIFICATION_REQUIRED = ("verified_by", "tested_at", "ontap_version", "environment")


def _err(errors: list[str], message: str) -> None:
    errors.append(message)


def _validate_owners(errors: list[str], prefix: str, owners: object) -> list[str] | None:
    if not isinstance(owners, list) or not owners:
        _err(errors, f"{prefix}: 'owners' must be a non-empty list")
        return None

    normalized: list[str] = []
    for index, owner in enumerate(owners):
        if not isinstance(owner, str) or not owner.strip():
            _err(errors, f"{prefix}.owners[{index}]: must be a non-empty string")
            continue
        if owner.startswith("@"):
            _err(errors, f"{prefix}.owners[{index}]: must not include '@' prefix")
            continue
        if not GITHUB_HANDLE.match(owner):
            _err(errors, f"{prefix}.owners[{index}]: invalid GitHub handle '{owner}'")
            continue
        normalized.append(owner.lower())

    if len(normalized) != len(set(normalized)):
        _err(errors, f"{prefix}: 'owners' must not contain duplicates (case-insensitive)")

    return normalized


def _validate_product(errors: list[str], prefix: str, use_case: dict) -> str | None:
    """Validate 'product'/'deployment' and return the path segment they imply.

    Returns None when the fields are unusable, so callers skip the path check
    rather than pile on redundant errors.
    """
    product = use_case.get("product")
    deployment = use_case.get("deployment")

    if product not in VALID_PRODUCTS:
        _err(errors, f"{prefix}: 'product' must be one of {sorted(VALID_PRODUCTS)}")
        return None

    allowed = VALID_DEPLOYMENTS.get(product)
    if deployment is None:
        if allowed:
            _err(
                errors,
                f"{prefix}: 'deployment' is required for product '{product}' "
                f"(one of {sorted(allowed)})",
            )
            return None
        return product

    if not allowed:
        _err(errors, f"{prefix}: product '{product}' has no deployment variants")
        return None
    if deployment not in allowed:
        _err(
            errors,
            f"{prefix}: 'deployment' must be one of {sorted(allowed)} for '{product}'",
        )
        return None

    return f"{product}/{deployment}"


def _validate_verification(
    errors: list[str],
    prefix: str,
    status: str,
    verification: object,
    owner_handles: list[str] | None,
) -> None:
    has_verification = verification is not None

    if status in {"draft", "deprecated"}:
        if has_verification:
            _err(
                errors,
                f"{prefix}: 'verification' must not be set when status is '{status}'",
            )
        return

    if status != "verified":
        return

    if not isinstance(verification, dict):
        _err(errors, f"{prefix}: 'verification' is required when status is 'verified'")
        return

    for field in VERIFICATION_REQUIRED:
        if field not in verification:
            _err(errors, f"{prefix}.verification: missing required field '{field}'")

    verified_by = verification.get("verified_by")
    if isinstance(verified_by, str) and verified_by.strip():
        if verified_by.startswith("@"):
            _err(errors, f"{prefix}.verification.verified_by: must not include '@' prefix")
        elif not GITHUB_HANDLE.match(verified_by):
            _err(
                errors,
                f"{prefix}.verification.verified_by: invalid GitHub handle '{verified_by}'",
            )
        elif owner_handles is not None and verified_by.lower() not in owner_handles:
            _err(
                errors,
                f"{prefix}.verification.verified_by: '{verified_by}' must be listed in owners",
            )
    else:
        _err(errors, f"{prefix}.verification.verified_by: must be a non-empty string")

    tested_at = verification.get("tested_at")
    if not isinstance(tested_at, str) or not ISO_DATE.match(tested_at):
        _err(errors, f"{prefix}.verification.tested_at: must be ISO date YYYY-MM-DD")

    ontap_version = verification.get("ontap_version")
    if not isinstance(ontap_version, str) or not ontap_version.strip():
        _err(errors, f"{prefix}.verification.ontap_version: must be a non-empty string")

    environment = verification.get("environment")
    if environment not in VALID_ENVIRONMENT:
        _err(
            errors,
            f"{prefix}.verification.environment: must be one of {sorted(VALID_ENVIRONMENT)}",
        )

    for optional in ("test_report", "notes"):
        value = verification.get(optional)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            _err(errors, f"{prefix}.verification.{optional}: must be a non-empty string")


def _discover_python() -> set[str]:
    """Scripts under python/, excluding the per-product shared REST clients."""
    return {
        str(p.relative_to(ROOT))
        for p in (ROOT / "python").rglob("*.py")
        if not p.name.endswith("_client.py")
    }


def _discover_ansible() -> set[str]:
    """Playbooks under ansible/, excluding collection and connection config."""
    return {
        str(p.relative_to(ROOT))
        for p in (ROOT / "ansible").rglob("*.yml")
        if p.name != "requirements.yml"
        and not {"inventory", "group_vars"} & set(p.relative_to(ROOT).parts)
    }


def _discover_terraform() -> set[str]:
    """Root module directories — any directory holding at least one .tf file."""
    return {str(p.parent.relative_to(ROOT)) for p in (ROOT / "terraform").rglob("*.tf")}


def _discover_go() -> set[str]:
    return {str(p.relative_to(ROOT)) for p in (ROOT / "go").rglob("main.go")}


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

        owner_handles = _validate_owners(errors, prefix, use_case.get("owners"))
        _validate_verification(
            errors,
            prefix,
            status if isinstance(status, str) else "",
            use_case.get("verification"),
            owner_handles,
        )

        description = use_case.get("description")
        if not isinstance(description, str) or not description.strip():
            _err(errors, f"{prefix}: 'description' must be a non-empty string")

        products = use_case.get("products")
        if not isinstance(products, list) or not products:
            _err(errors, f"{prefix}: 'products' must be a non-empty list")

        path_prefix = _validate_product(errors, prefix, use_case)

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
                _err(errors, f"{vprefix}: unknown tool (expected one of {sorted(VALID_TOOLS)})")
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
                if path_prefix and not path.startswith(f"{tool}/{path_prefix}/"):
                    _err(
                        errors,
                        f"{vprefix}: 'path' must start with '{tool}/{path_prefix}/', got: {path}",
                    )

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
    expected = _discover_python() | _discover_ansible() | _discover_terraform() | _discover_go()

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
        f"{len(_discover_terraform())} terraform, "
        f"{len(_discover_go())} go"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
