# YAML Workflows (Orchestrio CLI)

Declarative YAML workflow executor for ONTAP REST API automation. Define a
sequence of HTTP or shell steps in YAML, and the CLI handles template
resolution, retries, structured logging, and interactive debugging.

For the full CLI reference, workflow syntax, and plugin guide, see
[docs/orchestrio.md](../docs/orchestrio.md).

## Quick Start

```bash
cd yaml-workflows/executor
pip install -e ".[dev]"
cd ../..
orchestrio run yaml-workflows/workflows/cluster_info.yaml
```

## Directory Layout

```
yaml-workflows/
├── executor/             # Python CLI package (pip install -e .)
├── workflows/            # Production workflow YAML files
├── steps/                # Reusable step fragments (included via include:)
├── examples/             # Tutorial / demo workflows
├── workflow-spec/v1/     # JSON schema for the workflow format
├── logs/                 # Run logs (auto-created, git-ignored)
└── install.sh            # One-liner install script (curl)
```
