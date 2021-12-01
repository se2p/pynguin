#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.primitiveassertionobserver as pao
import pynguin.assertion.primitivetraceentry as pte


@pytest.mark.parametrize(
    "method, call_count",
    [
        ("visit_int_primitive_statement", 0),
        ("visit_float_primitive_statement", 0),
        ("visit_string_primitive_statement", 0),
        ("visit_bytes_primitive_statement", 0),
        ("visit_boolean_primitive_statement", 0),
        ("visit_none_statement", 0),
        ("visit_set_statement", 0),
        ("visit_list_statement", 0),
        ("visit_dict_statement", 0),
        ("visit_tuple_statement", 0),
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
    visitor = pao.PrimitiveAssertionVisitor(exec_ctx, variable, trace)
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
    visitor = pao.PrimitiveAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    with mock.patch.object(visitor, "handle"):
        with pytest.raises(NotImplementedError):
            getattr(visitor, method)(statement)


def test_handle_primitive():
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = 5
    variable = MagicMock()
    trace = MagicMock()
    visitor = pao.PrimitiveAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    statement.get_position.return_value = 42
    visitor.handle(statement)
    trace.add_entry.assert_called_with(42, pte.PrimitiveTraceEntry(variable, 5))


def test_handle_not_primitive():
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = MagicMock()
    variable = MagicMock()
    trace = MagicMock()
    visitor = pao.PrimitiveAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    visitor.handle(statement)
    trace.add_entry.assert_not_called()


def test_handle_none():
    exec_ctx = MagicMock()
    exec_ctx.get_variable_value.return_value = None
    variable = MagicMock()
    trace = MagicMock()
    visitor = pao.PrimitiveAssertionVisitor(exec_ctx, variable, trace)
    statement = MagicMock()
    visitor.handle(statement)
    trace.add_entry.assert_not_called()
