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
	ISORT_COMMAND_FLAG =
	MYPY_COMMAND_FLAG =
else
	POETRY_COMMAND_FLAG = -
	PIP_COMMAND_FLAG = -
	SECRETS_COMMAND_FLAG = -
	ISORT_COMMAND_FLAG = -
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

ifeq ($(ISORT_STRICT), 1)
	ISORT_COMMAND_FLAG =
else ifeq ($(ISORT_STRICT), 0)
	ISORT_COMMAND_FLAG = -
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
	$(ISORT_COMMAND_FLAG)poetry run isort --check-only .
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

.PHONY: isort
isort:
	poetry run isort .

.PHONY: ruff-format
ruff-format:
	poetry run ruff format .

.PHONY: check
check: isort mypy ruff ruff-format test

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
