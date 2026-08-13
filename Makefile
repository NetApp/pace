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
	$(PIP) install -q ruff pyyaml

# ── Mirrors ci.yml ─────────────────────────────────────────────

.PHONY: validate-catalog
validate-catalog: ## Validate catalog.yaml against repo examples
	$(PYTHON) scripts/validate_catalog.py

.PHONY: lint
lint: ## Ruff lint + format check (python examples)
	$(PYTHON) -m ruff check python/
	$(PYTHON) -m ruff format --check python/

.PHONY: ai-assets
ai-assets: ## Regenerate Copilot + Cursor assets from ai/
	$(PYTHON) scripts/generate_ai_assets.py

.PHONY: ai-assets-check
ai-assets-check: ## Fail if generated AI assets drift from ai/
	$(PYTHON) scripts/generate_ai_assets.py --self-test
	$(PYTHON) scripts/generate_ai_assets.py --check

.PHONY: ci
ci: lint validate-catalog ai-assets-check go-vet ## Run all core CI checks locally

# ── Mirrors validate-examples.yml ──────────────────────────────

# Examples live under <tool>/<product>/, so discovery below is recursive rather
# than a fixed-depth glob. A missing target is treated as a failure, otherwise a
# layout change would silently lint nothing.

.PHONY: go-vet
go-vet: ## Vet and build-check all Go programs
	cd go && go vet ./...
	@FOUND=0; \
	for dir in $$(find go -name main.go -exec dirname {} \; | sort); do \
		FOUND=$$((FOUND + 1)); \
		echo "Building $$dir …"; \
		(cd "$$dir" && go build -o /dev/null .) || exit 1; \
	done; \
	[ "$$FOUND" -gt 0 ] || { echo "error: no Go programs found under go/"; exit 1; }

.PHONY: ansible-lint
ansible-lint: ## Syntax-check and lint Ansible playbooks
	@FOUND=0; \
	for inv in $$(find ansible -path '*/inventory/hosts.yml' | sort); do \
		root=$$(dirname $$(dirname "$$inv")); \
		echo "=== $$root ==="; \
		for f in $$(find "$$root" -maxdepth 1 -name '*.yml' ! -name requirements.yml | sort); do \
			FOUND=$$((FOUND + 1)); \
			echo "Checking $$f …"; \
			ansible-playbook --syntax-check "$$f" -i "$$inv" || exit 1; \
		done; \
	done; \
	[ "$$FOUND" -gt 0 ] || { echo "error: no playbooks found under ansible/"; exit 1; }
	ansible-lint --profile min $$(find ansible -name '*.yml' ! -name requirements.yml \
		! -path '*/inventory/*' ! -path '*/group_vars/*' | sort)

.PHONY: terraform-validate
terraform-validate: ## Format-check, validate, and lint Terraform modules
	@ERRORS=0; \
	FOUND=0; \
	for dir in $$(find terraform -name '*.tf' -exec dirname {} \; | sort -u); do \
		FOUND=$$((FOUND + 1)); \
		echo "=== $$dir ==="; \
		terraform -chdir="$$dir" fmt -check || ERRORS=$$((ERRORS + 1)); \
		terraform -chdir="$$dir" init -backend=false -input=false > /dev/null 2>&1 || true; \
		terraform -chdir="$$dir" validate || ERRORS=$$((ERRORS + 1)); \
		tflint --chdir="$$dir" --no-color || true; \
		echo ""; \
	done; \
	[ "$$FOUND" -gt 0 ] || { echo "error: no Terraform modules found"; exit 1; }; \
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
