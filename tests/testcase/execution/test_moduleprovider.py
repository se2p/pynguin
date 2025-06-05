#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import sys

from unittest.mock import MagicMock

import pytest

import pynguin.testcase.execution as ex

# Needs to be loaded to be in sys.modules
import tests.fixtures.examples.module_alias  # noqa: F401

from tests.fixtures.examples import simple


@pytest.fixture
def module_provider() -> ex.ModuleProvider:
    return ex.ModuleProvider()


def test_load_module_normal(module_provider):
    result = module_provider.get_module("sys")
    assert result is not None


def test_load_module_custom(module_provider):
    module = MagicMock()
    module_provider.add_mutated_version("sys", module)
    result = module_provider.get_module("sys")
    assert result == module


def test_add_mutated_version(module_provider):
    module_provider.add_mutated_version("foo", MagicMock())
    assert module_provider._mutated_module_aliases.get("foo") is not None


def test_clear_mutated_modules(module_provider):
    module_provider.add_mutated_version("foo", MagicMock())
    module_provider.clear_mutated_modules()
    assert len(module_provider._mutated_module_aliases) == 0


def test_get_valid_module(module_provider):
    assert sys == module_provider.get_module("sys")


def test_get_invalid_module(module_provider):
    with pytest.raises(ex.ModuleNotImportedError):
        module_provider.get_module("foo")


def test_get_invalid_submodule(module_provider):
    with pytest.raises(ex.ModuleNotImportedError):
        module_provider.get_module("sys.foo")


def test_get_missing_submodule(module_provider):
    with pytest.raises(ex.ModuleNotImportedError):
        module_provider.get_module("tests.fixtures.examples.simple.foo")


def test_get_valid_module_with_alias(module_provider):
    assert simple == module_provider.get_module("tests.fixtures.examples.module_alias.deprecated")


def test_get_invalid_module_with_alias(module_provider):
    with pytest.raises(ex.ModuleNotImportedError):
        module_provider.get_module("tests.fixtures.examples.simple.add")
