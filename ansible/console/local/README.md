# Ansible — NetApp Console (local)

Placeholder for Ansible playbooks that automate NetApp Console in a `local`
deployment. **No playbooks live here yet** — this directory reserves the layout
so the first contribution has an obvious home.

## Adding the first playbook

1. Add `<use_case>.yml` in this directory, following the conventions in
   [`ansible/ontap/README.md`](../../ontap/README.md) and the skeleton in
   [`docs/example-template/ansible/example.yml`](../../../docs/example-template/ansible/example.yml).
2. Add `requirements.yml`, `inventory/hosts.yml`, and
   `group_vars/*.yml.example` here — Console connection details and collections
   are kept separate from ONTAP's.
3. Add a `use_cases` entry to [`catalog.yaml`](../../../catalog.yaml) with
   `product: console` and `deployment: local`. The variant `path` must be
   `ansible/console/local/<use_case>.yml` and `cwd` must be
   `ansible/console/local`; see [`docs/catalog-spec.md`](../../../docs/catalog-spec.md).
4. Replace this file with a real README documenting prerequisites, inputs, and
   outputs per section, matching the ONTAP README format.

CI discovers playbooks recursively, so a new file here is linted and
syntax-checked automatically once an inventory is present.
