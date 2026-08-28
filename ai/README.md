# AI instructions and prompts (source of truth)

Copilot and Cursor read different files, and the only file both read natively is
`AGENTS.md`. Instead of maintaining two parallel trees, everything is authored
once here and [`scripts/generate_ai_assets.py`](../scripts/generate_ai_assets.py)
renders each tool's dialect.

**Edit files in this directory, then run `make ai-assets`.** Never edit the
generated copies - each one carries a "do not edit" banner, and CI fails if they
drift from this tree.

## Layout

This tree mirrors the repository's own `<tool>/<product>/` convention, so a
prompt's product scope comes from where the file sits, not from frontmatter:

```
ai/
├── shared/                      # applies everywhere, no product scope
│   ├── repo-context.md          # kind: shared - repo-wide instructions
│   ├── review-contribution.md   # kind: task   - /review-contribution
│   └── prompt-catalog.md        # kind: doc    - docs/ai-prompt-catalog.md
├── ontap/
│   ├── conventions.md           # kind: product - attached under **/ontap/**
│   └── generate-python.md       # kind: task    - /ontap-generate-python
└── console/local/
    ├── conventions.md           # kind: product - attached under **/console/local/**
    └── prompt-catalog.md        # kind: doc    - docs/console-local-prompt-catalog.md
```

## Frontmatter

Two keys, and `kind` decides where the file lands:

```yaml
---
kind: task # shared | product | task
description: "One line shown in the command picker"
---
```

| `kind`    | Purpose                                 | Generates                                                       |
| --------- | --------------------------------------- | --------------------------------------------------------------- |
| `shared`  | Repo-wide context. Exactly one file.    | `AGENTS.md`, `.github/copilot-instructions.md`                  |
| `product` | Conventions auto-attached by file path  | `.github/instructions/<product>/…`, `.cursor/rules/<product>/…` |
| `task`    | A prompt invoked on demand              | `.github/prompts/<name>.prompt.md`, `.cursor/commands/<name>.md` |
| `doc`     | Human-facing docs that list the prompts | the single path given in `output`                               |

Optional keys: `globs` overrides the path-derived glob on a `product` file, and
`output` is required on a `doc` to say where it lands.

## Conventions when authoring

- **Write links repo-root-relative** - `[client](python/ontap/ontap_client.py)`
  rather than `[client](../../python/ontap/ontap_client.py)`. Outputs live at six
  different depths and the generator re-anchors every link for its destination.
  Links inside fenced code blocks are left alone.
- **Command names are flattened** to `<product>-<task>`, because both tools take
  a slash-command name from the filename and neither namespaces by folder.
  `ai/ontap/generate-python.md` becomes `/ontap-generate-python`.
- **Tokens expand to the prompt list**, so it is never written by hand:
  `{{PROMPT_INDEX}}` becomes a command-and-description table, and
  `{{PROMPT_FILES}}` adds a column linking each prompt's source file. Both work
  in any source body.

## Adding a product

1. Create `ai/<product>/conventions.md` with `kind: product`. The directory name
   must match an existing `<tool>/<product>/` directory - the generator checks.
2. Add task prompts beside it as `kind: task`.
3. Run `make ai-assets` and commit both the source and generated files.

## Checks

```bash
make ai-assets          # regenerate
make ai-assets-check    # what CI runs: self-test + drift check
```

The generator refuses to write anything if two prompts would flatten to the same
command name, if a product directory has no matching code, or if frontmatter is
missing or invalid.
