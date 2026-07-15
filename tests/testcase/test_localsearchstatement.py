#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Behavioural tests for the per-statement local-search strategies.

These exercise the strategy classes in
:mod:`pynguin.testcase.localsearchstatement`.  Rather than smoke-testing, each
test drives a strategy against a *stateful* objective that computes a real
fitness gradient from the current literal value, so the AVM-style hill climbers
actually converge (integers/floats to a target value, strings/bytes toward a
target shape) and the assertions check the committed statement afterwards.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.testcase.localsearchobjective import LocalSearchImprovement, LocalSearchObjective
from pynguin.testcase.localsearchstatement import (
    BooleanLocalSearch,
    BytesLocalSearch,
    CollectionLocalSearch,
    EnumLocalSearch,
    FloatLocalSearch,
    IntegerLocalSearch,
    ParametrizedStatementLocalSearch,
    StringLocalSearch,
    choose_local_search_statement,
    get_literal_value,
    randomize_literal_value,
    set_literal_value,
)
from pynguin.utils import randomness
from tests.testcase._builders import (
    assign,
    bytes_stmt,
    float_stmt,
    int_stmt,
    make_test_case,
    stmt,
    str_stmt,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _no_limit_timer() -> MagicMock:
    timer = MagicMock()
    timer.limit_reached.return_value = False
    return timer


def _stub_objective(improved=(), changed=()) -> MagicMock:
    """A canned objective whose has_improved/has_changed replay fixed sequences."""
    objective = MagicMock()
    objective.has_improved.side_effect = list(improved)
    objective.has_changed.side_effect = list(changed)
    return objective


class _FitnessObjective(LocalSearchObjective):
    """A stateful objective driven by a cost of the current literal value.

    ``cost`` is a minimisation metric; a move improves iff it strictly lowers
    the best cost seen so far.  This approximates the real objective closely enough
    for the AVM hill climbers, because the strategies restore any non-improving
    move, so the committed value always equals the current best.
    """

    def __init__(self, test_case, raw, cost):
        """Store the test case, the literal type, and the cost function."""
        self._test_case = test_case
        self._raw = raw
        self._cost = cost
        self._best = cost(self._read())

    def _read(self):
        return get_literal_value(self._test_case.get_statement(0), self._raw)

    @property
    def best(self) -> float:
        return self._best

    def has_changed(self, _chromosome) -> LocalSearchImprovement:
        value = self._read()
        if value is None:
            return LocalSearchImprovement.NONE
        cost = self._cost(value)
        if cost < self._best:
            self._best = cost
            return LocalSearchImprovement.IMPROVEMENT
        if cost > self._best:
            return LocalSearchImprovement.DETERIORATION
        return LocalSearchImprovement.NONE

    def has_improved(self, chromosome) -> bool:
        return self.has_changed(chromosome) == LocalSearchImprovement.IMPROVEMENT


def _chromosome(test_case) -> TestCaseChromosome:
    return TestCaseChromosome(test_case, None)


# ---------------------------------------------------------------------------
# Value-access helpers
# ---------------------------------------------------------------------------


def test_get_literal_value_none_for_multiple_targets():
    tc = make_test_case(stmt("var_0 = var_1 = 5"))
    assert get_literal_value(tc.get_statement(0), int) is None


def test_get_literal_value_none_for_non_literal_rhs():
    tc = make_test_case(assign("var_0", "len([])", bound_type=int))
    assert get_literal_value(tc.get_statement(0), int) is None


def test_get_literal_value_none_for_non_assignment():
    tc = make_test_case(stmt("assert var_0"))
    assert get_literal_value(tc.get_statement(0), int) is None


def test_set_literal_value_round_trip_preserves_metadata():
    tc = make_test_case(int_stmt("var_0", 5))
    assert set_literal_value(tc, 0, 42) is True
    assert get_literal_value(tc.get_statement(0), int) == 42
    assert tc.get_statement(0).bound_variable == "var_0"
    assert tc.get_statement(0).bound_type is int


def test_set_literal_value_false_when_unbound():
    # ``stmt`` does not set ``bound_variable`` -> RHS rewrite must refuse.
    tc = make_test_case(stmt("var_0 = 5"))
    assert set_literal_value(tc, 0, 7) is False


def test_randomize_literal_value_false_when_bound_type_none():
    tc = make_test_case(assign("var_0", "5"))
    assert randomize_literal_value(tc, 0) is False


def test_randomize_literal_value_keeps_type_and_binding():
    tc = make_test_case(str_stmt("var_0", "hello"))
    assert randomize_literal_value(tc, 0) is True
    assert tc.get_statement(0).bound_type is str
    assert get_literal_value(tc.get_statement(0), str) is not None


# ---------------------------------------------------------------------------
# Boolean
# ---------------------------------------------------------------------------


def test_boolean_local_search_flips_and_keeps_improvement():
    tc = make_test_case(assign("var_0", "False", bound_type=bool))
    search = BooleanLocalSearch(
        _chromosome(tc), 0, _stub_objective([True]), MagicMock(), MagicMock()
    )
    assert search.search() is True
    assert get_literal_value(tc.get_statement(0), bool) is True


def test_boolean_local_search_reverts_on_no_improvement():
    tc = make_test_case(assign("var_0", "True", bound_type=bool))
    search = BooleanLocalSearch(
        _chromosome(tc), 0, _stub_objective([False]), MagicMock(), MagicMock()
    )
    assert search.search() is False
    assert get_literal_value(tc.get_statement(0), bool) is True


def test_boolean_local_search_none_when_not_bool_literal():
    tc = make_test_case(assign("var_0", "len([])", bound_type=bool))
    search = BooleanLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock())
    assert search.search() is False


# ---------------------------------------------------------------------------
# Integer and float search
# ---------------------------------------------------------------------------


def test_integer_local_search_converges_to_target():
    tc = make_test_case(int_stmt("var_0", 0))
    objective = _FitnessObjective(tc, int, lambda v: abs(17 - v))
    search = IntegerLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.search() is True
    assert get_literal_value(tc.get_statement(0), int) == 17


def test_integer_local_search_false_when_not_int_literal():
    tc = make_test_case(assign("var_0", "len([])", bound_type=int))
    search = IntegerLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), _no_limit_timer())
    assert search.search() is False


def test_float_local_search_converges_to_target():
    tc = make_test_case(float_stmt("var_0", 0.0))
    objective = _FitnessObjective(tc, float, lambda v: abs(3.0 - v))
    search = FloatLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.search() is True
    assert get_literal_value(tc.get_statement(0), float) == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# String
# ---------------------------------------------------------------------------


def test_string_remove_chars_drops_only_helpful_characters():
    tc = make_test_case(str_stmt("var_0", "aXbXc"))
    # Fitness rewards removing the 'X' characters (fewer is better).
    objective = _FitnessObjective(tc, str, lambda v: v.count("X"))
    search = StringLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.remove_chars() is True
    assert get_literal_value(tc.get_statement(0), str) == "abc"


def test_string_replace_chars_avm_converges_to_target_char():
    tc = make_test_case(str_stmt("var_0", "c"))
    objective = _FitnessObjective(tc, str, lambda v: abs(ord(v[0]) - ord("a")) if v else 99)
    search = StringLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.replace_chars() is True
    assert get_literal_value(tc.get_statement(0), str) == "a"


def test_string_add_chars_grows_toward_target_length():
    tc = make_test_case(str_stmt("var_0", ""))
    objective = _FitnessObjective(tc, str, lambda v: abs(len(v) - 3))
    search = StringLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.add_chars() is True
    assert len(cast("str", get_literal_value(tc.get_statement(0), str))) == 3


def test_string_iterate_string_rejects_out_of_range_codepoint():
    tc = make_test_case(str_stmt("var_0", "\x00"))
    search = StringLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), _no_limit_timer())
    # ord('\x00') - 1 < 0 -> cannot move this code point down.
    assert search.iterate_string(0, -1) is False


def test_string_apply_random_mutations_false_when_no_fitness_change():
    tc = make_test_case(str_stmt("var_0", "hello"))
    objective = MagicMock()
    objective.has_changed.return_value = LocalSearchImprovement.NONE
    search = StringLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.apply_random_mutations() is False
    # Value is restored after every unhelpful probe.
    assert get_literal_value(tc.get_statement(0), str) == "hello"


def test_string_apply_random_mutations_true_on_change():
    tc = make_test_case(str_stmt("var_0", "hello"))
    objective = _stub_objective(changed=[LocalSearchImprovement.IMPROVEMENT])
    search = StringLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.apply_random_mutations() is True


def test_string_search_never_worsens_committed_fitness():
    randomness.RNG.seed(2024)
    tc = make_test_case(str_stmt("var_0", "zzz"))
    cost = lambda v: sum(abs(ord(c) - ord("a")) for c in v) + abs(len(v) - 3)  # noqa: E731
    initial = cost("zzz")
    objective = _FitnessObjective(tc, str, cost)
    search = StringLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    improved = search.search()
    assert isinstance(improved, bool)
    final = get_literal_value(tc.get_statement(0), str)
    assert cost(final) < initial


# ---------------------------------------------------------------------------
# Bytes
# ---------------------------------------------------------------------------


def test_bytes_remove_values_drops_only_helpful_bytes():
    tc = make_test_case(bytes_stmt("var_0", b"a\x00b\x00c"))
    objective = _FitnessObjective(tc, bytes, lambda v: v.count(0))
    search = BytesLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.remove_values() is True
    assert get_literal_value(tc.get_statement(0), bytes) == b"abc"


def test_bytes_replace_values_avm_converges_to_target_byte():
    tc = make_test_case(bytes_stmt("var_0", b"c"))
    objective = _FitnessObjective(tc, bytes, lambda v: abs(v[0] - ord("a")) if v else 255)
    search = BytesLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.replace_values() is True
    assert get_literal_value(tc.get_statement(0), bytes) == b"a"


def test_bytes_add_values_inserts_helpful_byte():
    tc = make_test_case(bytes_stmt("var_0", b""))
    objective = _FitnessObjective(tc, bytes, lambda v: abs(len(v) - 3))
    search = BytesLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.add_values() is True
    # A single insertion lowers the length penalty; the byte 97 ('a') is used.
    assert get_literal_value(tc.get_statement(0), bytes) == b"a"


def test_bytes_iterate_bytes_rejects_out_of_range_value():
    tc = make_test_case(bytes_stmt("var_0", b"\x00"))
    search = BytesLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), _no_limit_timer())
    assert search._iterate_bytes(0, -1) is False


def test_bytes_apply_random_mutations_false_when_no_fitness_change():
    tc = make_test_case(bytes_stmt("var_0", b"hello"))
    objective = MagicMock()
    objective.has_changed.return_value = LocalSearchImprovement.NONE
    search = BytesLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search._apply_random_mutations() is False
    assert get_literal_value(tc.get_statement(0), bytes) == b"hello"


def test_bytes_search_never_worsens_committed_fitness():
    randomness.RNG.seed(2024)
    tc = make_test_case(bytes_stmt("var_0", b"\xff\xff\xff"))
    cost = lambda v: sum(abs(b - ord("a")) for b in v) + abs(len(v) - 3)  # noqa: E731
    initial = cost(b"\xff\xff\xff")
    objective = _FitnessObjective(tc, bytes, cost)
    search = BytesLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    improved = search.search()
    assert isinstance(improved, bool)
    final = get_literal_value(tc.get_statement(0), bytes)
    assert cost(final) < initial


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------


def _enum_accessible(names, enum_name="Color") -> MagicMock:
    accessible = MagicMock(spec=gao.GenericEnum)
    accessible.names = list(names)
    owner = MagicMock()
    owner.name = enum_name
    accessible.owner = owner
    return accessible


def _enum_statement(names, member="RED"):
    statement = assign("var_0", f"module_0.Color.{member}")
    statement.accessible = _enum_accessible(names)
    return statement


def test_enum_local_search_selects_improving_member():
    tc = make_test_case(_enum_statement(["RED", "GREEN", "BLUE"], member="RED"))
    # GREEN does not improve, BLUE does -> BLUE is committed.
    objective = _stub_objective([False, True])
    search = EnumLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.search() is True
    assert EnumLocalSearch._current_member(tc.get_statement(0)) == "BLUE"


def test_enum_local_search_reverts_when_nothing_improves():
    tc = make_test_case(_enum_statement(["RED", "GREEN", "BLUE"], member="RED"))
    objective = _stub_objective([False, False])
    search = EnumLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.search() is False
    assert EnumLocalSearch._current_member(tc.get_statement(0)) == "RED"


def test_enum_local_search_false_when_accessible_not_enum():
    tc = make_test_case(assign("var_0", "module_0.Color.RED"))
    search = EnumLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), _no_limit_timer())
    assert search.search() is False


def test_enum_local_search_false_when_unbound_variable():
    statement = stmt("var_0 = module_0.Color.RED")  # bound_variable stays None
    statement.accessible = _enum_accessible(["RED", "GREEN"])
    tc = make_test_case(statement)
    search = EnumLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), _no_limit_timer())
    assert search.search() is False


def test_enum_local_search_false_when_no_names():
    tc = make_test_case(_enum_statement([], member="RED"))
    search = EnumLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), _no_limit_timer())
    assert search.search() is False


def test_enum_local_search_false_when_timer_exhausted():
    tc = make_test_case(_enum_statement(["RED", "GREEN"], member="RED"))
    timer = MagicMock()
    timer.limit_reached.return_value = True
    search = EnumLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), timer)
    assert search.search() is False


# ---------------------------------------------------------------------------
# Collections
# ---------------------------------------------------------------------------


def test_collection_local_search_keeps_improvement():
    tc = make_test_case(assign("var_0", "[]", bound_type=list))
    max_failures = config.configuration.local_search.ls_dict_max_insertions
    # First mutation improves; the following retries all fail -> stop.
    objective = _stub_objective([True] + [False] * (max_failures + 1))
    search = CollectionLocalSearch(_chromosome(tc), 0, objective, MagicMock(), _no_limit_timer())
    assert search.search() is True
    assert tc.get_statement(0).bound_type is list


def test_collection_local_search_false_for_non_collection_type():
    tc = make_test_case(int_stmt("var_0", 1))
    search = CollectionLocalSearch(_chromosome(tc), 0, MagicMock(), MagicMock(), _no_limit_timer())
    assert search.search() is False


# ---------------------------------------------------------------------------
# Parametrized statements (calls)
# ---------------------------------------------------------------------------


def _callable_statement():
    statement = assign("var_0", "Foo()")
    statement.accessible = MagicMock(spec=gao.GenericConstructor)
    return statement


def _call_factory() -> MagicMock:
    factory = MagicMock()
    factory.insert_random_statement.return_value = 1
    factory.mutate_call.return_value = True
    factory.change_random_call.return_value = True
    return factory


def test_parametrized_local_search_false_without_accessible():
    tc = make_test_case(assign("var_0", "None"))
    search = ParametrizedStatementLocalSearch(
        _chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock()
    )
    assert search.search() is False


def test_parametrized_local_search_false_when_no_improvement():
    randomness.RNG.seed(2024)
    tc = make_test_case(_callable_statement())
    objective = MagicMock()
    objective.has_improved.return_value = False
    search = ParametrizedStatementLocalSearch(
        _chromosome(tc), 0, objective, _call_factory(), _no_limit_timer()
    )
    assert search.search() is False
    # Exhausting the mutation budget hits every factory operation branch.
    assert objective.has_improved.call_count >= 1


def test_parametrized_local_search_true_on_improvement():
    randomness.RNG.seed(2024)
    tc = make_test_case(_callable_statement())
    timer = MagicMock()
    timer.limit_reached.side_effect = [False, True]
    objective = MagicMock()
    objective.has_improved.return_value = True
    search = ParametrizedStatementLocalSearch(_chromosome(tc), 0, objective, _call_factory(), timer)
    assert search.search() is True


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        (assign("var_0", "True", bound_type=bool), BooleanLocalSearch),
        (int_stmt("var_0", 3), IntegerLocalSearch),
        (float_stmt("var_0", 1.5), FloatLocalSearch),
        (str_stmt("var_0", "x"), StringLocalSearch),
        (bytes_stmt("var_0", b"x"), BytesLocalSearch),
        (assign("var_0", "[]", bound_type=list), CollectionLocalSearch),
        (assign("var_0", "{1}", bound_type=set), CollectionLocalSearch),
        (assign("var_0", "(1,)", bound_type=tuple), CollectionLocalSearch),
        (assign("var_0", "{}", bound_type=dict), CollectionLocalSearch),
    ],
)
def test_dispatch_primitive_and_collection(statement, expected):
    tc = make_test_case(statement)
    strategy = choose_local_search_statement(
        _chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock()
    )
    assert isinstance(strategy, expected)


def test_dispatch_bool_before_int():
    tc = make_test_case(assign("var_0", "True", bound_type=bool))
    strategy = choose_local_search_statement(
        _chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock()
    )
    assert isinstance(strategy, BooleanLocalSearch)


def test_dispatch_skips_primitive_with_non_literal_rhs():
    tc = make_test_case(assign("var_0", "len([])", bound_type=int))
    strategy = choose_local_search_statement(
        _chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock()
    )
    assert strategy is None


def test_dispatch_enum_accessible():
    tc = make_test_case(_enum_statement(["RED", "GREEN"], member="RED"))
    strategy = choose_local_search_statement(
        _chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock()
    )
    assert isinstance(strategy, EnumLocalSearch)


def test_dispatch_callable_accessible():
    tc = make_test_case(_callable_statement())
    strategy = choose_local_search_statement(
        _chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock()
    )
    assert isinstance(strategy, ParametrizedStatementLocalSearch)


def test_dispatch_returns_none_for_unsupported_statement():
    tc = make_test_case(assign("var_0", "None"))
    strategy = choose_local_search_statement(
        _chromosome(tc), 0, MagicMock(), MagicMock(), MagicMock()
    )
    assert strategy is None
