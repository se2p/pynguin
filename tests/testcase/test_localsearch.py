#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for the libcst-based local search re-implementation."""

from unittest.mock import MagicMock

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.testcase import literalgen
from pynguin.testcase.localsearch import TestCaseLocalSearch, TestSuiteLocalSearch
from pynguin.testcase.localsearchstatement import (
    BooleanLocalSearch,
    CollectionLocalSearch,
    ComplexLocalSearch,
    FieldStatementLocalSearch,
    IntegerLocalSearch,
    ParametrizedStatementLocalSearch,
    choose_local_search_statement,
    get_literal_value,
    randomize_literal_value,
    set_literal_value,
)
from pynguin.testcase.testcase import Statement, TestCase


def _assign_stmt(
    name: str, expr: cst.BaseExpression, *, bound_type: type | None = None
) -> Statement:
    node = cst.SimpleStatementLine(
        body=[cst.Assign(targets=[cst.AssignTarget(target=cst.Name(name))], value=expr)]
    )
    return Statement(node=node, bound_variable=name, bound_type=bound_type)


def _bool_case(*, value: bool) -> TestCase:
    tc = TestCase()
    tc.add_statement(_assign_stmt("var_0", cst.Name("True" if value else "False"), bound_type=bool))
    return tc


def _int_case(value: int) -> TestCase:
    tc = TestCase()
    tc.add_statement(_assign_stmt("var_0", literalgen.literal_to_cst(value), bound_type=int))
    return tc


def _fake_objective(results):
    """Builds a MagicMock LocalSearchObjective with canned has_improved/has_changed results."""
    objective = MagicMock()
    objective.has_improved.side_effect = list(results)
    objective.has_changed.side_effect = list(results)
    return objective


# ---------------------------------------------------------------------------
# literalgen value-access round trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        0,
        1,
        -5,
        3.5,
        -2.25,
        "",
        "hello",
        "ünïcödé",
        b"",
        b"\x00\xff",
        [1, 2],
        (1, 2),
        {1, 2},
        {"a": 1},
    ],
)
def test_literal_round_trip(value):
    expr = literalgen.literal_to_cst(value)
    raw = type(value)
    parsed = literalgen.parse_literal(expr, raw)
    assert parsed == value


def test_parse_literal_rejects_wrong_type():
    expr = cst.Integer("1")
    assert literalgen.parse_literal(expr, str) is None


# ---------------------------------------------------------------------------
# Value-access helpers
# ---------------------------------------------------------------------------


def test_get_set_literal_value_round_trip():
    tc = _int_case(5)
    assert get_literal_value(tc.get_statement(0), int) == 5
    assert set_literal_value(tc, 0, 42) is True
    assert get_literal_value(tc.get_statement(0), int) == 42
    # bound_variable/bound_type survive the RHS rewrite.
    assert tc.get_statement(0).bound_variable == "var_0"
    assert tc.get_statement(0).bound_type is int


def test_randomize_literal_value_changes_type_stays():
    tc = _int_case(5)
    assert randomize_literal_value(tc, 0) is True
    assert tc.get_statement(0).bound_type is int
    assert get_literal_value(tc.get_statement(0), int) is not None


# ---------------------------------------------------------------------------
# Strategy-level tests (stubbed objective)
# ---------------------------------------------------------------------------


def test_boolean_local_search_keeps_improvement():
    tc = _bool_case(value=False)
    chromosome = TestCaseChromosome(tc, None)
    objective = _fake_objective([True])
    search = BooleanLocalSearch(chromosome, 0, objective, MagicMock(), MagicMock())

    assert search.search() is True
    assert get_literal_value(tc.get_statement(0), bool) is True


def test_boolean_local_search_reverts_on_deterioration():
    tc = _bool_case(value=False)
    chromosome = TestCaseChromosome(tc, None)
    objective = _fake_objective([False])
    search = BooleanLocalSearch(chromosome, 0, objective, MagicMock(), MagicMock())

    assert search.search() is False
    assert get_literal_value(tc.get_statement(0), bool) is False


def test_integer_local_search_converges_towards_target():
    """A classic AVM scenario: fitness is the distance to 17; strict improvements only."""
    target = 17
    tc = _int_case(0)
    chromosome = TestCaseChromosome(tc, None)
    timer = MagicMock()
    timer.limit_reached.return_value = False

    objective = MagicMock()
    state = {"best": abs(target)}

    def has_improved(_chromosome):
        current = get_literal_value(tc.get_statement(0), int)
        if current is None:
            return False
        distance = abs(target - current)
        if distance < state["best"]:
            state["best"] = distance
            return True
        return False

    objective.has_improved.side_effect = has_improved

    search = IntegerLocalSearch(chromosome, 0, objective, MagicMock(), timer)
    improved = search.search()

    assert improved is True
    assert get_literal_value(tc.get_statement(0), int) == target


def test_collection_local_search_keeps_or_reverts():
    tc = TestCase()
    tc.add_statement(_assign_stmt("var_0", cst.List(elements=[]), bound_type=list))
    chromosome = TestCaseChromosome(tc, None)
    timer = MagicMock()
    timer.limit_reached.return_value = False
    # First mutation "improves"; all following retries "do not" -> stop after
    # ls_dict_max_insertions consecutive failures.
    max_failures = config.configuration.local_search.ls_dict_max_insertions
    objective = _fake_objective([True] + [False] * (max_failures + 1))

    search = CollectionLocalSearch(chromosome, 0, objective, MagicMock(), timer)
    improved = search.search()

    assert improved is True
    assert tc.get_statement(0).bound_type is list


def _complex_case(value: complex) -> TestCase:
    tc = TestCase()
    tc.add_statement(_assign_stmt("var_0", literalgen.literal_to_cst(value), bound_type=complex))
    return tc


def test_complex_local_search_keeps_improvement():
    tc = _complex_case(complex(1, 2))
    chromosome = TestCaseChromosome(tc, None)
    timer = MagicMock()
    timer.limit_reached.return_value = False
    # First mutation "improves"; all following retries "do not" -> stop after
    # ls_dict_max_insertions consecutive failures (mirrors the collection search).
    max_failures = config.configuration.local_search.ls_dict_max_insertions
    objective = _fake_objective([True] + [False] * (max_failures + 1))

    search = ComplexLocalSearch(chromosome, 0, objective, MagicMock(), timer)
    improved = search.search()

    assert improved is True
    assert tc.get_statement(0).bound_type is complex
    # The RHS is still a parseable complex literal after the search.
    assert get_literal_value(tc.get_statement(0), complex) is not None


def test_complex_local_search_non_literal_rhs_returns_false():
    tc = TestCase()
    tc.add_statement(
        _assign_stmt("var_0", cst.Call(func=cst.Name("foo"), args=[]), bound_type=complex)
    )
    chromosome = TestCaseChromosome(tc, None)
    search = ComplexLocalSearch(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert search.search() is False


def _field_statement(name: str = "var_0") -> Statement:
    stmt = _assign_stmt(name, cst.Attribute(value=cst.Name("var_1"), attr=cst.Name("attr")))
    stmt.accessible = MagicMock(spec=gao.GenericField)
    return stmt


def test_field_local_search_keeps_improvement():
    tc = TestCase()
    tc.add_statement(_field_statement())
    chromosome = TestCaseChromosome(tc, None)
    timer = MagicMock()
    timer.limit_reached.return_value = False
    factory = MagicMock()
    # First swap succeeds and improves; the second finds no further candidate.
    factory.change_random_field_call.side_effect = [True, False]
    objective = _fake_objective([True])

    search = FieldStatementLocalSearch(chromosome, 0, objective, factory, timer)

    assert search.search() is True
    assert objective.has_improved.call_count == 1


def test_field_local_search_reverts_on_no_improvement(monkeypatch):
    monkeypatch.setattr(
        config.configuration.local_search,
        "ls_random_parametrized_statement_call_count",
        3,
    )
    tc = TestCase()
    tc.add_statement(_field_statement())
    chromosome = TestCaseChromosome(tc, None)
    timer = MagicMock()
    timer.limit_reached.return_value = False
    factory = MagicMock()
    factory.change_random_field_call.return_value = True
    objective = MagicMock()
    objective.has_improved.return_value = False

    search = FieldStatementLocalSearch(chromosome, 0, objective, factory, timer)

    assert search.search() is False
    # Exhausts all allowed attempts, restoring after each non-improving swap.
    assert factory.change_random_field_call.call_count == 3


def test_field_local_search_no_field_accessible_returns_false():
    tc = TestCase()
    tc.add_statement(_assign_stmt("var_0", cst.Name("None")))
    chromosome = TestCaseChromosome(tc, None)
    search = FieldStatementLocalSearch(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert search.search() is False


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def test_choose_local_search_statement_bool_before_int():
    tc = _bool_case(value=True)
    chromosome = TestCaseChromosome(tc, None)
    strategy = choose_local_search_statement(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert isinstance(strategy, BooleanLocalSearch)


def test_choose_local_search_statement_skips_non_literal_rhs():
    """bound_type=int but the RHS is not a literal (e.g. a call result) -> skip."""
    tc = TestCase()
    tc.add_statement(_assign_stmt("var_0", cst.Call(func=cst.Name("len"), args=[]), bound_type=int))
    chromosome = TestCaseChromosome(tc, None)
    strategy = choose_local_search_statement(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert strategy is None


def test_choose_local_search_statement_complex():
    tc = _complex_case(complex(3, -1))
    chromosome = TestCaseChromosome(tc, None)
    strategy = choose_local_search_statement(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert isinstance(strategy, ComplexLocalSearch)


def test_choose_local_search_statement_complex_non_literal_rhs():
    tc = TestCase()
    tc.add_statement(
        _assign_stmt("var_0", cst.Call(func=cst.Name("f"), args=[]), bound_type=complex)
    )
    chromosome = TestCaseChromosome(tc, None)
    strategy = choose_local_search_statement(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert strategy is None


def test_choose_local_search_statement_field():
    tc = TestCase()
    tc.add_statement(_field_statement())
    chromosome = TestCaseChromosome(tc, None)
    strategy = choose_local_search_statement(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert isinstance(strategy, FieldStatementLocalSearch)


def test_choose_local_search_statement_parametrized():
    tc = TestCase()
    accessible = MagicMock(spec=gao.GenericConstructor)
    stmt = _assign_stmt("var_0", cst.Call(func=cst.Name("Foo"), args=[]))
    stmt.accessible = accessible
    tc.add_statement(stmt)
    chromosome = TestCaseChromosome(tc, None)
    strategy = choose_local_search_statement(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert isinstance(strategy, ParametrizedStatementLocalSearch)


def test_parametrized_local_search_no_accessible_returns_false():
    tc = TestCase()
    tc.add_statement(_assign_stmt("var_0", cst.Name("None")))
    chromosome = TestCaseChromosome(tc, None)
    search = ParametrizedStatementLocalSearch(chromosome, 0, MagicMock(), MagicMock(), MagicMock())
    assert search.search() is False


# ---------------------------------------------------------------------------
# TestCaseLocalSearch orchestration
# ---------------------------------------------------------------------------


def test_check_statement_type_enabled_primitives_default(monkeypatch):
    monkeypatch.setattr(config.configuration.local_search, "local_search_primitives", True)
    monkeypatch.setattr(config.configuration.local_search, "local_search_collections", False)
    monkeypatch.setattr(config.configuration.local_search, "local_search_complex_objects", False)
    tc = _int_case(1)
    assert TestCaseLocalSearch._check_statement_type_enabled(tc.get_statement(0)) is True


def test_local_search_visits_statements_with_probability_one(monkeypatch):
    monkeypatch.setattr(config.configuration.local_search, "local_search_probability", 1.0)
    monkeypatch.setattr(config.configuration.local_search, "local_search_same_datatype", True)
    monkeypatch.setattr(config.configuration.local_search, "local_search_different_datatype", False)
    monkeypatch.setattr(config.configuration.local_search, "local_search_llm", False)

    tc = _int_case(1)
    chromosome = TestCaseChromosome(tc, None)
    timer = MagicMock()
    timer.limit_reached.return_value = False
    objective = MagicMock()
    objective.has_improved.return_value = False

    search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    # Should not raise, even though no factory/executor machinery is wired up.
    search.local_search(chromosome, MagicMock(), objective)


def test_search_different_datatype_returns_true_on_improvement():
    tc = _int_case(1)
    chromosome = TestCaseChromosome(tc, None)
    chromosome.set_last_execution_result(MagicMock())

    timer = MagicMock()
    timer.limit_reached.return_value = False
    factory = MagicMock()
    factory.change_statement_type.return_value = True
    objective = MagicMock()
    objective.has_improved.return_value = True

    search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    # Avoid running the real same-datatype machinery once an improvement is found.
    search._search_same_datatype = MagicMock(return_value=True)

    assert search._search_different_datatype(chromosome, factory, objective, 0) is True
    factory.change_statement_type.assert_called_once_with(chromosome.test_case, 0)
    search._search_same_datatype.assert_called_once_with(chromosome, factory, objective, 0)


def test_search_different_datatype_returns_false_when_no_improvement(monkeypatch):
    monkeypatch.setattr(config.configuration.local_search, "ls_max_different_type_mutations", 3)
    tc = _int_case(1)
    chromosome = TestCaseChromosome(tc, None)
    chromosome.set_last_execution_result(MagicMock())

    timer = MagicMock()
    timer.limit_reached.return_value = False
    factory = MagicMock()
    factory.change_statement_type.return_value = False
    objective = MagicMock()
    objective.has_improved.return_value = False

    search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)

    assert search._search_different_datatype(chromosome, factory, objective, 0) is False
    # The mutation loop should have exhausted all allowed attempts.
    assert factory.change_statement_type.call_count == search._max_mutations


# ---------------------------------------------------------------------------
# TestSuiteLocalSearch.double_branch_coverage
# ---------------------------------------------------------------------------


def test_double_branch_coverage_duplicates_singly_covered_predicates():
    tc = _int_case(1)
    chromosome = TestCaseChromosome(tc, None)
    execution_result = MagicMock()
    execution_result.execution_trace.executed_predicates = {0: 1, 1: 2}
    chromosome.set_last_execution_result(execution_result)

    suite = TestSuiteChromosome()
    suite.add_test_case_chromosome(chromosome)

    TestSuiteLocalSearch().double_branch_coverage(suite)

    # Predicate 0 was covered exactly once -> one duplicate test case is added.
    assert len(suite.test_case_chromosomes) == 2


def test_double_branch_coverage_no_duplicates_when_all_covered_twice():
    tc = _int_case(1)
    chromosome = TestCaseChromosome(tc, None)
    execution_result = MagicMock()
    execution_result.execution_trace.executed_predicates = {0: 2}
    chromosome.set_last_execution_result(execution_result)

    suite = TestSuiteChromosome()
    suite.add_test_case_chromosome(chromosome)

    TestSuiteLocalSearch().double_branch_coverage(suite)

    assert len(suite.test_case_chromosomes) == 1


# ---------------------------------------------------------------------------
# Regression guard: importing/wiring local search must not crash (see
# DISABLED_SUBSYSTEMS.md #1).
# ---------------------------------------------------------------------------


def test_local_search_modules_are_importable():
    import pynguin.testcase.llmlocalsearch  # noqa: PLC0415
    import pynguin.testcase.localsearch  # noqa: PLC0415
    import pynguin.testcase.localsearchstatement  # noqa: PLC0415

    assert pynguin.testcase.localsearch is not None
    assert pynguin.testcase.llmlocalsearch is not None
    assert pynguin.testcase.localsearchstatement is not None
