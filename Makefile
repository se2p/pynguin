# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

SHELL := /usr/bin/env bash
IMAGE := pynguin
VERSION=$(shell git rev-parse --short HEAD)

ifeq ($(STRICT), 1)
	POETRY_COMMAND_FLAG =
	PIP_COMMAND_FLAG =
	SECRETS_COMMAND_FLAG =
	MYPY_COMMAND_FLAG =
else
	POETRY_COMMAND_FLAG = -
	PIP_COMMAND_FLAG = -
	SECRETS_COMMAND_FLAG = -
	MYPY_COMMAND_FLAG = -
endif

ifeq ($(POETRY_STRICT), 1)
	POETRY_COMMAND_FLAG =
else ifeq ($(POETRY_STRICT), 0)
	POETRY_COMMAND_FLAG = -
endif

ifeq ($(PIP_STRICT), 1)
	PIP_COMMAND_FLAG =
else ifeq ($(PIP_STRICT), 0)
	PIP_COMMAND_FLAG = -
endif

ifeq ($(SECRETS_STRICT), 1)
	SECRETS_COMMAND_FLAG =
else ifeq ($(SECRETS_STRICT), 0)
	SECRETS_COMMAND_FLAG = -
endif

ifeq ($(MYPY_STRICT), 1)
	MYPY_COMMAND_FLAG =
else ifeq ($(MYPY_STRICT), 0)
	MYPY_COMMAND_FLAG = -
endif


.PHONY: download-poetry
download-poetry:
	curl -sSL https://install.python-poetry.org | python3 -

.PHONY: install
install:
	poetry lock -n
	poetry install -n
ifneq ($(NO_PRE_COMMIT), 1)
	poetry run pre-commit install
endif

.PHONY: check-safety
check-safety:
	$(POETRY_COMMAND_FLAG)poetry check
	$(PIP_COMMAND_FLAG)pip check

.PHONY: check-style
check-style:
	$(MYPY_COMMAND_FLAG)poetry run mypy

.PHONY: codestyle
codestyle:
	poetry run pre-commit run --all-files

.PHONY: test
test:
	poetry run pytest --cov=src --cov=tests --cov-report=term-missing --cov-report html:cov_html tests/

.PHONY: mypy
mypy:
	poetry run mypy

.PHONY: ruff
ruff:
	poetry run ruff check src/pynguin

.PHONY: ruff-format
ruff-format:
	poetry run ruff format .

.PHONY: check
check: mypy ruff ruff-format test

.PHONY: lint
lint: test check-safety check-style

.PHONY: documentation
documentation:
	poetry run sphinx-build docs docs/_build

.PHONY: docker
docker:
	@echo Building docker $(IMAGE):$(VERSION) ...
	docker build \
	  -t $(IMAGE):$(VERSION) . \
	  -f ./docker/Dockerfile --no-cache

.PHONY: clean_docker
clean_docker:
	@echo Removing docker $(IMAGE):$(VERSION) ...
	docker rmi -f $(IMAGE):$(VERSION)

.PHONY: clean_build
clean_build:
	rm -rf build/
	rm -rf .hypothesis
	rm -rf .mypy_cache
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf cov_html
	rm -rf dist
	rm -rf docs/_build
	find . -name pynguin-report -type d | xargs rm -rf {};
	find . -name ".coverage*" -type f | xargs rm -rf {};
	find . -name "*.pyc" -type f | xargs rm -rf {};

.PHONY: clean
clean: clean_build clean_docker

PYVERSIONS = 3.10 3.11 3.12 3.13 3.14

.PHONY: setup-envs
setup-envs:
	@for v in $(PYVERSIONS); do \
		echo "=== Setting up .venv-$$v ==="; \
		pyenv local $$v; \
		python -m venv .venv-$$v; \
		. .venv-$$v/bin/activate; \
		poetry install --extras "openai numpy fandango-faker"; \
		deactivate; \
	done
	@echo "=== All environments created ==="

define activate_template
	@echo "Activating .venv-$(1)..."
	@bash --rcfile <(echo "source .venv-$(1)/bin/activate") -i
endef

.PHONY: py310 py311 py312 py313 py314
py310:
	$(call activate_template,3.10)

py311:
	$(call activate_template,3.11)

py312:
	$(call activate_template,3.12)

py313:
	$(call activate_template,3.13)

py314:
	$(call activate_template,3.14)

define test_template
	@echo "Running tests in .venv-$(1)..."
	@bash -c 'source .venv-$(1)/bin/activate && pytest'
endef

.PHONY: py310-test py311-test py312-test py313-test py314-test
py310-test:
	$(call test_template,3.10)

py311-test:
	$(call test_template,3.11)

py312-test:
	$(call test_template,3.12)

py313-test:
	$(call test_template,3.13)

py314-test:
	$(call test_template,3.14)
