# Copilot Instructions for Orchestrio

## Project overview

This repository contains ONTAP automation examples in Python, Ansible, and Terraform,
alongside Orchestrio — a no-code/low-code CLI tool for automating NetApp resource
workflows using ONTAP REST APIs. The workflow spec is language-agnostic (YAML/JSON);
the Python package under `yaml-workflows/executor/` is the reference executor.

## Key concepts

- **Workflow**: a YAML file with `name`, `version`, optional `env`/`defaults`, and a
  `steps` array.
- **Step**: atomic unit — has a `name`, `type` (`http` | `shell` | custom), and `config` dict.
- **Step Fragment**: reusable single-step YAML in `yaml-workflows/steps/`, imported via `include:`.
- **Template**: `{{ steps.<name>.<path> }}` references prior step output;
  `{{ env.KEY }}` references an environment variable.
- **Defaults**: type-level config merged into every step of that type (deep merge,
  step-level wins).

## Repository layout

```
python/                 # Python script examples (primary)
ansible/                # Ansible playbook examples (primary)
terraform/              # Terraform module examples (primary)
yaml-workflows/
  executor/
    orchestrio/
      cli.py            # Click CLI (run, validate)
      engine.py         # template resolution + step orchestration
      parser.py         # YAML/JSON loader + include resolution
      models.py         # Pydantic v2 data models
      env_loader.py     # env file loading + merge logic
      run_logger.py     # structured JSONL run logger
      utils.py          # deep_merge, walk_path helpers
      plugins/
        base.py         # abstract StepPlugin + @register decorator
        http.py         # HTTP/REST plugin (httpx, polling, auth)
        shell.py        # shell subprocess plugin
    tests/              # pytest test suite
  workflows/            # production workflow YAML files
  steps/                # reusable step fragments
  examples/             # tutorial / demo workflows
  workflow-spec/v1/     # JSON schema for the workflow format
docs/                   # guides and comparison documentation
```

## Coding conventions

- Python >= 3.11; use modern syntax (PEP 604 unions, f-strings, `match` where appropriate).
- Pydantic v2 for all data models. Use `model_dump_json()` not `.json()`.
- Async execution: plugins are `async def execute(...)`.
- Linter: `ruff` (line length 99, target py311). Run `ruff check yaml-workflows/executor/orchestrio/`.
- Tests: `pytest` with `pytest-asyncio` (auto mode). Tests live in `yaml-workflows/executor/tests/`.
- Step names and fragment filenames use `snake_case`.
- Workflow YAML uses the schema at `yaml-workflows/workflow-spec/v1/schema.json`.

## Creating a new plugin

1. Create `yaml-workflows/executor/orchestrio/plugins/my_type.py`.
2. Subclass `StepPlugin`, decorate with `@StepPlugin.register("my_type")`.
3. Implement `async def execute(self, step, context) -> StepResult`.
4. Import it in `plugins/__init__.py` so it auto-registers.

## Creating a workflow

1. Create a `.yaml` file with `name`, `version`, and `steps`.
2. Each step needs `name` (snake_case), `type`, and `config`.
3. Use `{{ env.VAR }}` for credentials; supply via `--env-file` or `--env`.
4. Use `{{ steps.<name>.<path> }}` to chain step outputs.
5. Validate with `orchestrio validate <file>` before running.
