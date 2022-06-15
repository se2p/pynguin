#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock, call

import pytest

import pynguin.ga.postprocess as pp
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt


def test_not_failing():
    trunc = pp.ExceptionTruncation()
    test_case = MagicMock()
    chromosome = MagicMock(test_case=test_case)
    chromosome.is_failing.return_value = False
    trunc.visit_test_case_chromosome(chromosome)
    test_case.chop.assert_not_called()


def test_simple_chop():
    trunc = pp.ExceptionTruncation()
    test_case = MagicMock()
    chromosome = MagicMock(test_case=test_case)
    chromosome.is_failing.return_value = True
    chromosome.get_last_mutatable_statement.return_value = 42
    trunc.visit_test_case_chromosome(chromosome)
    test_case.chop.assert_called_once_with(42)


def test_suite_chop():
    trunc = pp.ExceptionTruncation()
    chromosome = MagicMock()
    suite = MagicMock(test_case_chromosomes=[chromosome, chromosome])
    trunc.visit_test_suite_chromosome(suite)
    chromosome.accept.assert_has_calls([call(trunc), call(trunc)])


def test_suite_assertion_minimization():
    ass_min = pp.AssertionMinimization()
    chromosome = MagicMock()
    suite = MagicMock(test_case_chromosomes=[chromosome, chromosome])
    ass_min.visit_test_suite_chromosome(suite)
    chromosome.accept.assert_has_calls([call(ass_min), call(ass_min)])


def test_test_case_assertion_minimization():
    ass_min = pp.AssertionMinimization()
    test_case = dtc.DefaultTestCase()
    statement = stmt.IntPrimitiveStatement(test_case)

    assertion_1 = MagicMock(
        checked_instructions=[MagicMock(lineno=1), MagicMock(lineno=2)]
    )
    assertion_2 = MagicMock(checked_instructions=[MagicMock(lineno=1)])

    statement.add_assertion(assertion_1)
    statement.add_assertion(assertion_2)
    test_case.add_statement(statement)

    chromosome = tcc.TestCaseChromosome(test_case=test_case)
    ass_min.visit_test_case_chromosome(chromosome)

    assert ass_min.remaining_assertions == {assertion_1}
    assert ass_min.deleted_assertions == {assertion_2}
    assert test_case.get_assertions() == [assertion_1]


def test_test_case_postprocessor_suite():
    dummy_visitor = MagicMock()
    tcpp = pp.TestCasePostProcessor([dummy_visitor])
    chromosome = MagicMock()
    suite = MagicMock(test_case_chromosomes=[chromosome, chromosome])
    tcpp.visit_test_suite_chromosome(suite)
    chromosome.accept.assert_has_calls([call(tcpp), call(tcpp)])


def test_test_case_postprocessor_test():
    dummy_visitor = MagicMock()
    tcpp = pp.TestCasePostProcessor([dummy_visitor])
    test_case = MagicMock()
    test_chromosome = MagicMock(test_case=test_case)
    tcpp.visit_test_case_chromosome(test_chromosome)
    test_case.accept.assert_has_calls([call(dummy_visitor)])


def test_unused_primitives_visitor():
    visitor = pp.UnusedStatementsTestCaseVisitor()
    statement = MagicMock()
    test_case = MagicMock(statements=[statement])
    visitor.visit_default_test_case(test_case)
    assert statement.accept.call_count == 1


def test_remove_integration(constructor_mock):
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(stmt.IntPrimitiveStatement(test_case))
    test_case.add_statement(stmt.FloatPrimitiveStatement(test_case))
    int0 = stmt.IntPrimitiveStatement(test_case)
    test_case.add_statement(int0)
    list0 = stmt.ListStatement(test_case, list[int], [int0.ret_val])
    test_case.add_statement(list0)
    float0 = stmt.FloatPrimitiveStatement(test_case)
    test_case.add_statement(float0)
    ctor0 = stmt.ConstructorStatement(
        test_case, constructor_mock, {"foo": float0.ret_val, "bar": list0.ret_val}
    )
    test_case.add_statement(ctor0)
    assert test_case.size() == 6
    visitor = pp.UnusedStatementsTestCaseVisitor()
    test_case.accept(visitor)
    assert test_case.statements == [int0, list0, float0, ctor0]


@pytest.mark.parametrize(
    "statement_type, func",
    [
        ("visit_int_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_float_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_string_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_bytes_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_boolean_primitive_statement", "_handle_collection_or_primitive"),
        ("visit_enum_statement", "_handle_collection_or_primitive"),
        ("visit_none_statement", "_handle_collection_or_primitive"),
        ("visit_constructor_statement", "_handle_remaining"),
        ("visit_method_statement", "_handle_remaining"),
        ("visit_function_statement", "_handle_remaining"),
        ("visit_list_statement", "_handle_collection_or_primitive"),
        ("visit_set_statement", "_handle_collection_or_primitive"),
        ("visit_tuple_statement", "_handle_collection_or_primitive"),
        ("visit_dict_statement", "_handle_collection_or_primitive"),
    ],
)
def test_all_statements(statement_type, func):
    visitor = pp.UnusedPrimitiveOrCollectionStatementVisitor()
    with mock.patch.object(visitor, func) as func:
        visitor.__getattribute__(statement_type)(MagicMock())
        func.assert_called_once()


@pytest.mark.parametrize(
    "statement_type",
    [
        "visit_field_statement",
        "visit_assignment_statement",
    ],
)
def test_not_implemented_statements(statement_type):
    visitor = pp.UnusedPrimitiveOrCollectionStatementVisitor()
    with pytest.raises(NotImplementedError):
        visitor.__getattribute__(statement_type)(MagicMock())
