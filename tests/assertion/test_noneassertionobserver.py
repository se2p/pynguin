#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.noneassertionobserver as nao
import pynguin.assertion.nonetraceentry as nte


@pytest.mark.parametrize(
    "method, call_count",
    [
        ("visit_int_primitive_statement", 0),
        ("visit_float_primitive_statement", 0),
        ("visit_string_primitive_statement", 0),
        ("visit_boolean_primitive_statement", 0),
        ("visit_none_statement", 0),
        ("visit_constructor_statement", 1),
        ("visit_method_statement", 1),
        ("visit_function_statement", 1),
    ],
)
def test_visits(method, call_count):
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = 5
    variable = MagicMock()
    trace = MagicMock()
    visitor = nao.NoneAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    with mock.patch.object(visitor, "handle") as handle_mock:
        getattr(visitor, method)(statement)
        assert handle_mock.call_count == call_count


@pytest.mark.parametrize(
    "method",
    [
        "visit_field_statement",
        "visit_assignment_statement",
    ],
)
def test_visits_unimplemented(method):
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = 5
    variable = MagicMock()
    trace = MagicMock()
    visitor = nao.NoneAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    with mock.patch.object(visitor, "handle"):
        with pytest.raises(NotImplementedError):
            getattr(visitor, method)(statement)


def test_handle_primitive():
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = 5
    variable = MagicMock()
    trace = MagicMock()
    visitor = nao.NoneAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    visitor.handle(statement)
    trace.add_entry.assert_not_called()


def test_handle_not_primitive():
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = MagicMock()
    variable = MagicMock()
    trace = MagicMock()
    visitor = nao.NoneAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    statement.get_position.return_value = 42
    visitor.handle(statement)
    trace.add_entry.assert_called_with(
        42, variable, nte.NoneTraceEntry(variable, False)
    )


def test_handle_not_primitive_none():
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = None
    variable = MagicMock()
    trace = MagicMock()
    visitor = nao.NoneAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    statement.get_position.return_value = 42
    visitor.handle(statement)
    trace.add_entry.assert_called_with(42, variable, nte.NoneTraceEntry(variable, True))
