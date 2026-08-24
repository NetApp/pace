# Catalog Explorer

Static HTML generated from the repo-root `catalog.yaml`. GitHub Pages serves
`docs/` from `main`, so the live page is:

**https://netapp.github.io/pace/catalog/**

Do not edit `docs/catalog/index.html` by hand. Change `catalog.yaml` or the
templates under `scripts/catalog/` and regenerate.

## Generate locally

From the repository root (after `make install`):

```bash
make catalog-site
```

Or:

```bash
.venv/bin/python scripts/catalog/build_catalog_site.py
```

Then open `docs/catalog/index.html` in a browser. The default view is the card
grid; use Cards / Table / Graph in the control row.

The command is idempotent: it overwrites `docs/catalog/index.html` and copies
vendored `vis-network` into `docs/catalog/vendor/`.

Optional flags:

```bash
.venv/bin/python scripts/catalog/build_catalog_site.py \
  --catalog catalog.yaml \
  --output docs/catalog/index.html
```

A malformed or incomplete catalog exits non-zero and does not write HTML
(validation runs before render).

## CI

`.github/workflows/catalog-site.yml` regenerates the site when `catalog.yaml`
or `scripts/catalog/` changes. On `main` it commits `docs/catalog/` if the
output changed. Pull requests only generate (no commit).
