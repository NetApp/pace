# Python — NetApp Console (local)

Placeholder for Python scripts that automate NetApp Console in a `local`
deployment. **No scripts live here yet** — this directory reserves the layout so
the first contribution has an obvious home.

## Adding the first script

1. Add `<use_case>.py` in this directory, following the conventions in
   [`python/ontap/README.md`](../../ontap/README.md) and the skeleton in
   [`docs/example-template/python/example.py`](../../../docs/example-template/python/example.py).
2. Add a `requirements.txt` and a `console_client.py` here — the shared REST
   client is per product, so scripts import it as a sibling module
   (`from console_client import ...`) exactly as ONTAP scripts import
   `ontap_client`.
3. Add a `use_cases` entry to [`catalog.yaml`](../../../catalog.yaml) with
   `product: console` and `deployment: local`. The variant `path` must be
   `python/console/local/<use_case>.py` and `cwd` must be
   `python/console/local`; see [`docs/catalog-spec.md`](../../../docs/catalog-spec.md).
4. Replace this file with a real README documenting prerequisites, inputs, and
   outputs per section, matching the ONTAP README format.

Ruff lints `python/` recursively, so a new script here is checked automatically.
Modules named `*_client.py` are treated as shared clients and excluded from
catalog coverage.
