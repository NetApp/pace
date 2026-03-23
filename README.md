# Orchestrio

Define workflows in YAML. Execute them via CLI.

The workflow spec is **language-agnostic** — decoupled from the executor so any language can implement it.
The Python executor is the reference implementation.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git

### Step-by-step

```bash
# 1. Clone the repo
git clone https://github.com/<org>/orchestrio.git
cd orchestrio

# 2. (Optional) Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install the Python executor in editable mode
cd executors/python
pip install -e .

# 4. Verify the install
orchestrio --help

# 5. Validate the example workflow
orchestrio validate ../../examples/hello.yaml

# 6. Run it
orchestrio run ../../examples/hello.yaml
```

**Expected output** — the engine fetches a random joke from a public API, then echoes a message:

```
✓ step fetch_joke   → 200 OK
✓ step print_result → Joke fetched successfully!
```

Add `-v` for debug-level logging:

```bash
orchestrio run ../../examples/hello.yaml -v
```

---

## How It Works

```
workflow-spec/v1/schema.json   ← language-agnostic schema
examples/hello.yaml            ← sample workflows
executors/python/              ← Python executor (CLI + REST API)
```

1. You write a workflow in YAML (or JSON) following the spec.
2. The executor parses it, resolves templates, and runs each step via plugins (`http`, `shell`, etc.).
3. Steps can reference outputs from earlier steps with `{{ steps.<name>.<path> }}`.

---

## Workflow Basics

```yaml
name: hello-world
version: "1"
steps:
  - name: fetch_joke
    type: http
    config:
      method: GET
      url: https://official-joke-api.appspot.com/random_joke
    retry:
      attempts: 2
      delay_seconds: 1

  - name: print_result
    type: shell
    config:
      command: echo "Joke fetched successfully!"
```

### Template syntax

Reference earlier step outputs with `{{ steps.<step_name>.<path> }}`:

| Expression | Resolves to |
|---|---|
| `{{ steps.fetch_joke.body.setup }}` | JSON body field |
| `{{ steps.fetch_joke.status_code }}` | HTTP status code |
| `{{ steps.run_cmd.stdout }}` | Shell stdout |
| `{{ env.MY_VAR }}` | Workflow-level env variable |

---

## Custom Plugins

```python
from orchestrio.plugins.base import StepPlugin
from orchestrio.models import StepDefinition, StepResult, StepStatus

@StepPlugin.register("my_type")
class MyPlugin(StepPlugin):
    async def execute(self, step, context):
        return StepResult(name=step.name, status=StepStatus.SUCCESS, output={...})
```

Register it in `orchestrio/plugins/__init__.py`.

---

## License

MIT
