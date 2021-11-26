#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

from pynguin.testcase.execution import ExecutionContext, ModuleProvider


def test_get_variable_value_variable_not_known():
    test_var = MagicMock()
    ctx = ExecutionContext(ModuleProvider())
    with pytest.raises(ValueError):
        ctx.get_variable_value(test_var)


def test_get_variable_value_variable_has_no_value():
    test_var = MagicMock()
    ctx = ExecutionContext(ModuleProvider())
    ctx._variable_names.get_name(test_var)
    with pytest.raises(ValueError):
        ctx.get_variable_value(test_var)


def test_get_variable_value_success():
    test_var = MagicMock()
    ctx = ExecutionContext(ModuleProvider())
    name = ctx._variable_names.get_name(test_var)
    ctx._local_namespace[name] = "foo"
    assert ctx.get_variable_value(test_var) == "foo"
