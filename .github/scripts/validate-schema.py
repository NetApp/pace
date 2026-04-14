#!/usr/bin/env python3
"""Validate YAML workflow files against the Orchestrio JSON schema."""

import glob
import json
import sys

import yaml
from jsonschema import ValidationError, validate

SCHEMA_PATH = "yaml-workflows/workflow-spec/v1/schema.json"
YAML_GLOBS = [
    "yaml-workflows/examples/*.yaml",
    "yaml-workflows/workflows/*.yaml",
]


def main() -> int:
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)

    files = sorted(p for g in YAML_GLOBS for p in glob.glob(g))
    if not files:
        print("No YAML files found to validate")
        return 0

    errors = 0
    for path in files:
        with open(path) as f:
            doc = yaml.safe_load(f)
        try:
            validate(instance=doc, schema=schema)
            print(f"  OK  {path}")
        except ValidationError as e:
            print(f"  FAIL  {path}: {e.message}")
            errors += 1

    if errors:
        print(f"\n{errors} file(s) failed schema validation")
        return 1

    print(f"\nAll {len(files)} file(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
