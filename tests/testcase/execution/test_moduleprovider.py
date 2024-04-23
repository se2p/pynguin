#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.execution as ex


@pytest.fixture()
def module_provider() -> ex.ModuleProvider:
    return ex.ModuleProvider()


def test_load_module_normal(module_provider):
    result = module_provider.get_module("sys")
    assert result is not None


def test_load_module_custom(module_provider):
    module = MagicMock()
    transformer = MagicMock()
    module_provider.add_mutated_version("sys", module, transformer)
    result = module_provider.get_module("sys")
    assert result == module


def test_add_mutated_version(module_provider):
    transformer = MagicMock()
    module_provider.add_mutated_version("foo", MagicMock(), transformer)
    assert module_provider._mutated_module_aliases.get("foo") is not None


def test_clear_mutated_modules(module_provider):
    transformer = MagicMock()
    module_provider.add_mutated_version("foo", MagicMock(), transformer)
    module_provider.clear_mutated_modules()
    assert len(module_provider._mutated_module_aliases) == 0
