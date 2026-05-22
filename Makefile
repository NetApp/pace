.DEFAULT_GOAL := help
SHELL := /bin/bash

VENV   := .venv
PYTHON := $(VENV)/bin/python
PIP    := $(VENV)/bin/pip

# ── Setup ──────────────────────────────────────────────────────

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PIP) install -q --upgrade pip

.PHONY: install
install: $(VENV)/bin/activate ## Create venv and install dev deps
	$(PIP) install -q ruff

# ── Mirrors ci.yml ─────────────────────────────────────────────

.PHONY: lint
lint: ## Ruff lint + format check (python examples)
	$(PYTHON) -m ruff check python/
	$(PYTHON) -m ruff format --check python/

.PHONY: ci
ci: lint ## Run all core CI checks locally

# ── Mirrors validate-examples.yml ──────────────────────────────

.PHONY: ansible-lint
ansible-lint: ## Syntax-check and lint Ansible playbooks
	@for f in ansible/*.yml; do \
		[ "$$(basename "$$f")" = "requirements.yml" ] && continue; \
		echo "Checking $$f …"; \
		ansible-playbook --syntax-check "$$f" -i ansible/inventory/hosts.yml; \
	done
	ansible-lint ansible/*.yml --exclude ansible/requirements.yml

.PHONY: terraform-validate
terraform-validate: ## Format-check, validate, and lint Terraform modules
	@ERRORS=0; \
	for dir in terraform/*/; do \
		echo "=== $$(basename "$$dir") ==="; \
		terraform -chdir="$$dir" fmt -check || ERRORS=$$((ERRORS + 1)); \
		terraform -chdir="$$dir" init -backend=false -input=false > /dev/null 2>&1 || true; \
		terraform -chdir="$$dir" validate || ERRORS=$$((ERRORS + 1)); \
		tflint --chdir="$$dir" --no-color || true; \
		echo ""; \
	done; \
	[ "$$ERRORS" -eq 0 ] || exit 1

# ── Docker ─────────────────────────────────────────────────────

.PHONY: docker-build
docker-build: ## Build the dev container
	docker build -t pace-dev .

.PHONY: docker-ci
docker-ci: docker-build ## Run CI checks inside the container
	docker run --rm pace-dev make ci

# ── Pre-commit hooks ───────────────────────────────────────────

.PHONY: hooks
hooks: ## Install pre-commit hooks into your local repo
	pre-commit install --hook-type pre-commit --hook-type commit-msg --hook-type pre-push

# ── Help ───────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Docs ───────────────────────────────────────────────────────
.PHONY: troubleshoot
troubleshoot: ## Show numbered index of troubleshooting sections
	@echo "The Troubleshooting Guide"
	@echo ""
	@awk '/^## / { if (heading) printf "%2d. %s\n    Tip: %s\n\n", ++count, heading, tip; heading=substr($$0,4); tip="" } /^### / && heading && !tip { tip=substr($$0,5) } END { if (heading) printf "%2d. %s\n    Tip: %s\n\n", ++count, heading, tip }' docs/troubleshooting.md