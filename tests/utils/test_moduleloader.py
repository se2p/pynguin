#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.utils.moduleloader as ml


def test_load_module_normal():
    result = ml.ModuleLoader.load_module("sys")
    assert result is not None


def test_load_module_custom():
    module = MagicMock()
    ml.ModuleLoader.add_mutated_version("sys", module)
    result = ml.ModuleLoader.load_module("sys")
    assert result == module
    ml.ModuleLoader.clear_mutated_modules()


def test_add_mutated_version():
    ml.ModuleLoader.add_mutated_version("foo", MagicMock())
    assert ml.ModuleLoader._mutated_module_aliases.get("foo") is not None


def test_clear_mutated_modules():
    ml.ModuleLoader.add_mutated_version("foo", MagicMock())
    ml.ModuleLoader.clear_mutated_modules()
    assert len(ml.ModuleLoader._mutated_module_aliases) == 0
