#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.execution as ex


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


def test_module_not_imported(module_provider):
    with pytest.raises(ex.ModuleNotImportedError):
        module_provider.get_module("foo")
