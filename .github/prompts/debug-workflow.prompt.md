# Debug a Failing Orchestrio Workflow

Given a workflow YAML file and the error output (CLI stderr, JSON result, or JSONL log),
diagnose the failure and suggest a fix.

> For ONTAP REST API conventions (endpoints, response shapes, status codes),
> invoke `/ontap-rest-api` or see `docs/ontap-api-patterns.md`.

## Diagnostic checklist

1. **Validation errors** — Run `orchestrio validate <file>` first. Check for:
   - Missing required fields (`name`, `version`, `steps`)
   - Invalid step names (must match `^[a-zA-Z_][a-zA-Z0-9_]*$`)
   - Unknown step types (only `http` and `shell` are built-in)

2. **Template resolution failures** — Look for unresolved `{{ }}` expressions:
   - Typo in step name: `{{ steps.get_cluser.body }}` vs `get_cluster`
   - Referencing a step that runs later or was skipped
   - Missing env var: `{{ env.ONTAP_HOST }}` when no value is set

3. **HTTP errors** — Check the `StepResult` output:
   - `status_code` 401/403: wrong credentials or missing auth config
   - `status_code` 404: wrong URL or API path (verify against the ONTAP REST API spec)
   - Connection error: host unreachable, DNS failure, or `verify_ssl` not set to `false`

4. **Shell errors** — Check `stdout`, `stderr`, and `exit_code` in the step result.

5. **Retry exhaustion** — Step failed on all attempts. Check `attempts` count in the result
   and consider increasing `retry.attempts` or `retry.delay_seconds`.

6. **on_failure: stop** — A prior step failed and halted the workflow. Later steps show
   status `skipped`. Fix the failing step or set `on_failure: continue` if it's non-critical.

7. **Env layering** — Precedence: `--env` > `--env-file` > `os.environ` > YAML `env:` defaults.
   A value might be overridden unexpectedly.

## Output format

1. State the root cause in one sentence.
2. Show the specific line(s) in the YAML that need changing.
3. Provide the corrected YAML snippet.
4. Suggest a command to verify the fix (e.g., `orchestrio run --dry-run` or `orchestrio validate`).
