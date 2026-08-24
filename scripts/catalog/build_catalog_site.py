#!/usr/bin/env python3
# © 2026 NetApp, Inc. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
# See the NOTICE file in the repo root for trademark and attribution details.

"""Generate the static Catalog Explorer HTML from catalog.yaml.

Validates the catalog first (fail-loud), then renders
scripts/catalog/templates/index.html.j2 into docs/catalog/index.html.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print("error: PyYAML is required — install with: pip install pyyaml", file=sys.stderr)
    sys.exit(2)

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except ImportError:
    print("error: Jinja2 is required — install with: pip install jinja2", file=sys.stderr)
    sys.exit(2)

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS_DIR))

from validate_catalog import CATALOG_PATH, ROOT, validate_catalog  # noqa: E402

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "index.html.j2"
VENDOR_SRC = Path(__file__).resolve().parent / "vendor"
VENDOR_FILES = ("vis-network.min.js",)
DEFAULT_OUTPUT = ROOT / "docs" / "catalog" / "index.html"

EXPLORER_REQUIRED = (
    "id",
    "description",
    "owners",
    "status",
    "variants",
)


def _explorer_errors(data: object) -> list[str]:
    """Extra fail-loud checks used by the site builder."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["catalog root must be a mapping"]

    use_cases = data.get("use_cases")
    if not isinstance(use_cases, list) or not use_cases:
        return ["'use_cases' must be a non-empty list"]

    for index, use_case in enumerate(use_cases):
        prefix = f"use_cases[{index}]"
        if not isinstance(use_case, dict):
            errors.append(f"{prefix}: must be a mapping")
            continue
        for field in EXPLORER_REQUIRED:
            value = use_case.get(field)
            if value is None or value == "" or value == [] or value == {}:
                errors.append(f"{prefix}: missing or empty required field '{field}'")
    return errors


def load_catalog(path: Path) -> dict:
    if not path.is_file():
        print(f"error: missing {path}", file=sys.stderr)
        sys.exit(1)

    with path.open(encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            print(f"error: catalog.yaml is malformed: {exc}", file=sys.stderr)
            sys.exit(1)

    errors = validate_catalog(data)
    errors.extend(_explorer_errors(data))
    if errors:
        print(f"catalog validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for message in errors:
            print(f"  - {message}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print("error: catalog root must be a mapping", file=sys.stderr)
        sys.exit(1)
    return data


def copy_vendor(dest_dir: Path) -> None:
    vendor_dest = dest_dir / "vendor"
    vendor_dest.mkdir(parents=True, exist_ok=True)
    for name in VENDOR_FILES:
        src = VENDOR_SRC / name
        if not src.is_file():
            print(f"error: missing vendored file {src}", file=sys.stderr)
            sys.exit(1)
        shutil.copy2(src, vendor_dest / name)


def render_site(data: dict, output: Path, generated_at: str) -> None:
    if not (TEMPLATE_DIR / TEMPLATE_NAME).is_file():
        print(f"error: missing template {TEMPLATE_DIR / TEMPLATE_NAME}", file=sys.stderr)
        sys.exit(1)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(TEMPLATE_NAME)
    html = template.render(
        use_cases=data["use_cases"],
        generated_at=generated_at,
        vis_js_src="vendor/vis-network.min.js",
        template_name=f"scripts/catalog/templates/{TEMPLATE_NAME}",
        source_catalog="catalog.yaml",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    copy_vendor(output.parent)
    output.write_text(html, encoding="utf-8")
    print(f"wrote {output.relative_to(ROOT)} ({len(data['use_cases'])} use cases)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Catalog Explorer static site")
    parser.add_argument(
        "--catalog",
        type=Path,
        default=CATALOG_PATH,
        help="Path to catalog.yaml (default: repo-root catalog.yaml)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output HTML path (default: docs/catalog/index.html)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog_path = args.catalog if args.catalog.is_absolute() else ROOT / args.catalog
    output = args.output if args.output.is_absolute() else ROOT / args.output

    display = catalog_path
    if catalog_path.is_relative_to(ROOT):
        display = catalog_path.relative_to(ROOT)
    print(f"loading {display}", flush=True)
    data = load_catalog(catalog_path)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    render_site(data, output, generated_at)
    return 0


if __name__ == "__main__":
    sys.exit(main())
