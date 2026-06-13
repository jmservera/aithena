SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON_SERVICES ?= $(sort $(foreach p,$(wildcard src/*/pyproject.toml),$(if $(wildcard $(dir $(p))tests),$(notdir $(patsubst %/,%,$(dir $(p)))))))
UI_DIR ?= src/aithena-ui
E2E_DIR ?= e2e
PLAYWRIGHT_DIR ?= e2e/playwright
STRESS_DIR ?= tests/stress
E2E ?= 0
STRESS ?= 0

PYTEST_CMD ?= uv run pytest
PYTEST_ARGS ?= --tb=short -q
E2E_PYTEST_CMD ?= pytest
E2E_PYTEST_ARGS ?= -v --tb=short
VITEST_CMD ?= npx vitest
VITEST_ARGS ?= run
PLAYWRIGHT_CMD ?= npx playwright test
PLAYWRIGHT_ARGS ?=
STRESS_PYTEST_CMD ?= python -m pytest
STRESS_PYTEST_ARGS ?= -v --tb=short --timeout=600

HAS_UI := $(if $(wildcard $(UI_DIR)/package.json),yes,no)
HAS_E2E := $(if $(wildcard $(E2E_DIR)/pytest.ini),yes,no)
HAS_PLAYWRIGHT := $(if $(wildcard $(PLAYWRIGHT_DIR)/package.json),yes,no)
HAS_STRESS := $(if $(wildcard $(STRESS_DIR)/pytest.ini),yes,no)

PYTHON_TEST_TARGETS := $(addprefix test-,$(PYTHON_SERVICES))
PYTHON_LINT_TARGETS := $(addprefix lint-,$(PYTHON_SERVICES))
PYTHON_FORMAT_TARGETS := $(addprefix format-,$(PYTHON_SERVICES))

ifneq ($(HAS_UI),no)
UI_TEST_TARGETS := test-ui-unit
UI_LINT_TARGETS := lint-ui
UI_FORMAT_TARGETS := format-ui
endif

ifeq ($(E2E),1)
ifneq ($(HAS_PLAYWRIGHT),no)
UI_TEST_TARGETS += test-ui-e2e
endif
endif

ALL_TEST_TARGETS := test-backend

ifneq ($(HAS_UI),no)
ALL_TEST_TARGETS += test-ui
endif

ifeq ($(STRESS),1)
ifneq ($(HAS_STRESS),no)
ALL_TEST_TARGETS += test-stress-python
endif
endif

.PHONY: help test test-backend test-ui test-ui-unit test-ui-e2e test-playwright test-e2e test-e2e-python test-stress test-stress-python lint format lint-ui format-ui $(PYTHON_TEST_TARGETS) $(PYTHON_LINT_TARGETS) $(PYTHON_FORMAT_TARGETS)

help: ## List available targets
	@printf "\nAvailable targets:\n\n"
	@printf "  %-22s %s\n" "help" "List available targets"
	@printf "  %-22s %s\n" "test" "Run backend and default UI suites (E2E=1, STRESS=1 to opt in)"
	@printf "  %-22s %s\n" "test-backend" "Run pytest for all Python backend services"
	@if [ "$(HAS_UI)" != "no" ]; then printf "  %-22s %s\n" "test-ui" "Run UI Vitest suite (set E2E=1 to include Playwright)"; fi
	@if [ "$(HAS_UI)" != "no" ]; then printf "  %-22s %s\n" "test-ui-unit" "Run UI Vitest suite"; fi
	@if [ "$(HAS_E2E)" != "no" ]; then printf "  %-22s %s\n" "test-e2e" "Run Python and browser end-to-end suites"; fi
	@if [ "$(HAS_E2E)" != "no" ]; then printf "  %-22s %s\n" "test-e2e-python" "Run Python end-to-end suite"; fi
	@if [ "$(HAS_PLAYWRIGHT)" != "no" ]; then printf "  %-22s %s\n" "test-ui-e2e" "Run Playwright end-to-end suite"; fi
	@if [ "$(HAS_PLAYWRIGHT)" != "no" ]; then printf "  %-22s %s\n" "test-playwright" "Alias for test-ui-e2e"; fi
	@if [ "$(HAS_STRESS)" != "no" ]; then printf "  %-22s %s\n" "test-stress-python" "Run Python stress tests (requires stack)"; fi
	@if [ "$(HAS_STRESS)" != "no" ]; then printf "  %-22s %s\n" "test-stress" "Alias for test-stress-python"; fi
	@printf "  %-22s %s\n" "lint" "Run Ruff and ESLint"
	@printf "  %-22s %s\n" "format" "Run Ruff format and Prettier"
	@if [ "$(HAS_UI)" != "no" ]; then printf "  %-22s %s\n" "lint-ui" "Run ESLint for the UI"; fi
	@if [ "$(HAS_UI)" != "no" ]; then printf "  %-22s %s\n" "format-ui" "Run Prettier for the UI"; fi
	@for svc in $(PYTHON_SERVICES); do \
		printf "  %-22s %s\n" "test-$$svc" "Run pytest for $$svc"; \
		printf "  %-22s %s\n" "lint-$$svc" "Run Ruff for $$svc"; \
		printf "  %-22s %s\n" "format-$$svc" "Run Ruff format for $$svc"; \
	done

test: $(ALL_TEST_TARGETS) ## Run all available test suites

test-backend: $(PYTHON_TEST_TARGETS) ## Run pytest for all Python backend services

test-ui: $(UI_TEST_TARGETS) ## Run UI Vitest suite; include Playwright with E2E=1

test-e2e: test-e2e-python test-ui-e2e ## Run Python and browser end-to-end suites

test-playwright: test-ui-e2e ## Alias for Playwright end-to-end tests

test-stress: test-stress-python ## Alias for Python stress tests

lint: $(PYTHON_LINT_TARGETS) $(UI_LINT_TARGETS) ## Run Ruff and ESLint

format: $(PYTHON_FORMAT_TARGETS) $(UI_FORMAT_TARGETS) ## Run Ruff format and Prettier

test-ui-unit: ## Run UI Vitest suite
	@echo "==> Running UI unit tests (Vitest)"
	@cd $(UI_DIR) && \
		if [ ! -d node_modules ] && [ -f package-lock.json ]; then npm ci; fi && \
		$(VITEST_CMD) $(VITEST_ARGS)

test-e2e-python: ## Run Python end-to-end suite
	@echo "==> Running Python E2E tests"
	@cd $(E2E_DIR) && $(E2E_PYTEST_CMD) $(E2E_PYTEST_ARGS)

test-ui-e2e: ## Run Playwright end-to-end suite
	@echo "==> Running browser E2E tests (Playwright)"
	@cd $(PLAYWRIGHT_DIR) && \
		if [ ! -d node_modules ] && [ -f package-lock.json ]; then npm ci; fi && \
		$(PLAYWRIGHT_CMD) $(PLAYWRIGHT_ARGS)

test-stress-python: ## Run Python stress tests (requires a running stack)
	@echo "==> Running stress tests"
	@python -m pip install --upgrade pip
	@python -m pip install -r $(STRESS_DIR)/requirements-stress.txt
	@cd $(STRESS_DIR) && $(STRESS_PYTEST_CMD) $(STRESS_PYTEST_ARGS)

lint-ui: ## Run ESLint for the UI
	@cd $(UI_DIR) && \
		if [ ! -d node_modules ] && [ -f package-lock.json ]; then npm ci; fi && \
		npm run lint

format-ui: ## Run Prettier for the UI
	@cd $(UI_DIR) && \
		if [ ! -d node_modules ] && [ -f package-lock.json ]; then npm ci; fi && \
		npm run format

define PYTHON_SERVICE_RULES

test-$(1): ## Run pytest for $(1)
	@echo "==> Running backend tests for $(1)"
	@cd src/$(1) && $(PYTEST_CMD) $(PYTEST_ARGS)

lint-$(1): ## Run Ruff for $(1)
	@ruff check src/$(1)

format-$(1): ## Run Ruff format for $(1)
	@ruff format src/$(1)

endef

$(foreach svc,$(PYTHON_SERVICES),$(eval $(call PYTHON_SERVICE_RULES,$(svc))))
