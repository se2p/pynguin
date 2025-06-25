#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import sys

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pynguin.testcase.localsearchstatement import FloatLocalSearch, ComplexLocalSearch
from pynguin.testcase.localsearchstatement import IntegerLocalSearch
from pynguin.testcase.localsearchstatement import StringLocalSearch
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import FloatPrimitiveStatement, ComplexPrimitiveStatement
from pynguin.testcase.statement import IntPrimitiveStatement
from pynguin.testcase.statement import StringPrimitiveStatement


@pytest.fixture(autouse=True)
def setup_timer():
    timer = LocalSearchTimer.get_instance()
    timer.limit_reached = MagicMock(return_value=False)


def test_iterate_success() -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()

    objective.has_improved.side_effect = [True] * 3 + [False]

    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, 1, 2)


def test_iterate_fail() -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]

    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, 1, 2) is False


@pytest.mark.parametrize(
    "value, delta, increasing_factor, iterations, final_result",
    [(2, 1, 2, 5, 33), (39, 4, 23, 3, 2251), (128, 0, 3, 10, 128)],
)
def test_iterate_int_value(value, delta, increasing_factor, iterations, final_result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * iterations + [False]
    statement = IntPrimitiveStatement(chromosome, value)
    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, delta, increasing_factor)
    assert statement.value == final_result


def test_iterate_float_value() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 3 + [False]
    statement = FloatPrimitiveStatement(chromosome, 2.56)
    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, 1.5, 1.5)
    assert statement.value == 9.685


@pytest.mark.parametrize(
    "value, result, side_effect",
    [
        (4, 6, [True] * 2 + [False] * 2 + [True] + [False] * 3),
        (4, 12, [True] * 3 + [False] + [True] + [False] * 3),
        (4, -27, [False] + [True] * 5 + [False] * 3),
        (7, -27, [False] + [True] * 5 + [False] * 2 + [True] * 2 + [False] * 3),
        (7, -21, [False] + [True] * 5 + [False] + [True] * 2 + [False] * 3),
        (-511, 0, [True] * 9 + [False] * 3),
        (0, 0, [False] * 2),
    ],
)
def test_int_search(value, result, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = IntPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(3)]
    chromosome.test_case.statements[2] = statement
    local_search = IntegerLocalSearch()
    local_search.search(chromosome, 2, objective)
    assert statement.value == result


@pytest.mark.parametrize(
    "value, result, objective_effect",
    [
        (
            1.0,
            2.5,
            [True]
            + [False] * 3
            + [True] * 3
            + [False] * 2
            + [True] * 2
            + [False]
            + [True]
            + [False] * 100,
        ),
        (
            1.0,
            2.22,
            [True]
            + [False] * 3
            + [True] * 2
            + [False] * 2
            + [True]
            + [False] * 3
            + [True] * 2
            + [False] * 2
            + [True]
            + [False] * 100,
        ),
    ],
)
def test_float_search(value, result, objective_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = objective_effect
    objective.has_changed.return_value = 0
    statement = FloatPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = FloatLocalSearch()
    local_search.search(chromosome, 1, objective)
    assert statement.value == result

@pytest.mark.parametrize(
    "value, result, objective_effect",
    [
        (complex(1.0,1.0),complex(2.0,1.0), [True]+[False]*10),

    ],
)
def test_complex_search_real_part(value, result, objective_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = objective_effect
    objective.has_changed.return_value = 0
    statement = ComplexPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = ComplexLocalSearch()
    local_search.search(chromosome, 1, objective)
    assert statement.value.real == result.real
    assert statement.value.imag == result.imag

def test_apply_random_mutations_fail() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = 0

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective) is False


def test_apply_random_mutations_success() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [1]

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective)


def test_apply_random_mutations_negative_success() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = -1

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective)


def test_apply_random_mutations_improves() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = 1
    statement = StringPrimitiveStatement(chromosome, "testString")

    def side_effect():
        statement.value = "String1"

    statement.randomize_value = MagicMock(side_effect=side_effect)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement
    statement.value = "testString"

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective)
    assert statement.value == "String1"


def test_apply_random_mutations_worsens() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = -1
    statement = StringPrimitiveStatement(chromosome, "testString")

    def side_effect():
        statement.value = "String1"

    statement.randomize_value = MagicMock(side_effect=side_effect)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement
    statement.value = "testString"

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective)
    assert statement.value == "testString"


def test_remove_chars() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False] + [True] + [False] * 10

    statement = StringPrimitiveStatement(chromosome, "testString")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch()
    local_search.remove_chars(chromosome, 4, objective)
    assert statement.value == "testStrig"


def test_remove_chars2() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False] + [True] * 2 + [False] * 10

    statement = StringPrimitiveStatement(chromosome, "testing")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch()
    local_search.remove_chars(chromosome, 4, objective)
    assert statement.value == "testg"


def test_remove_chars_all() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 20

    statement = StringPrimitiveStatement(chromosome, "test")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch()
    local_search.remove_chars(chromosome, 4, objective)
    assert statement.value == ""  # noqa: PLC1901


def test_remove_chars_none() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False] * 20

    statement = StringPrimitiveStatement(chromosome, "This should stay")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch()
    local_search.remove_chars(chromosome, 4, objective)
    assert statement.value == "This should stay"


def test_iterate_string_fail() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]
    statement = StringPrimitiveStatement(chromosome, "test")

    string_local_search = StringLocalSearch()
    assert not string_local_search.iterate_string(chromosome, statement, objective, 3, 2)


@pytest.mark.parametrize(
    "value, result, delta, char_position",
    [
        ("test", "uest", 1, 0),
        ("test", "sest", -1, 0),
        ("test", "tewt", 4, 2),
        ("test", "test", 0, 0),
        ("test", "tess", -1, 3),
    ],
)
def test_iterate_string(value, result, delta, char_position) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, value)
    objective.has_improved.side_effect = [True, False]

    string_local_search = StringLocalSearch()
    assert string_local_search.iterate_string(
        chromosome, statement, objective, char_position, delta
    )
    assert statement.value == result


@pytest.mark.parametrize(
    "value, result, side_effect",
    [("test", "west", [True] * 2 + [False]), ("test", "{est", [True] * 3 + [False])],
)
def test_iterate_string_multiple_iterations(value, result, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, value)
    objective.has_improved.side_effect = side_effect

    string_local_search = StringLocalSearch()
    assert string_local_search.iterate_string(chromosome, statement, objective, 0, 1)
    assert statement.value == result


@pytest.mark.parametrize(
    "delta",
    [(-1000000), 10000000],
)
def test_iterate_string_bounds(delta) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, "test")
    objective.has_improved.side_effect = [True, False]

    string_local_search = StringLocalSearch()
    assert not string_local_search.iterate_string(chromosome, statement, objective, 0, delta)
    assert statement.value == "test"


def test_iterate_string_lower_bound_second_iteration() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, chr(1))
    objective.has_improved.side_effect = [True] * 10 + [False]

    string_local_search = StringLocalSearch()
    assert string_local_search.iterate_string(chromosome, statement, objective, 0, -1)
    assert statement.value == chr(0)


def test_iterate_string_upper_bound_second_iteration() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, chr(sys.maxunicode - 1))
    objective.has_improved.side_effect = [True] * 10 + [False]

    string_local_search = StringLocalSearch()
    assert string_local_search.iterate_string(chromosome, statement, objective, 0, 1)
    assert statement.value == chr(sys.maxunicode)


def test_iterate_string_timer(monkeypatch) -> None:
    with patch.object(LocalSearchTimer, "_instance", None):
        monkeypatch.setattr("pynguin.config.LocalSearchConfiguration.local_search_time", -1)
        chromosome = MagicMock()
        objective = MagicMock()
        objective.has_improved.side_effect = [True] * 10 + [False]
        statement = StringPrimitiveStatement(chromosome, "test")
        timer = LocalSearchTimer.get_instance()
        timer.start_local_search()

        string_local_search = StringLocalSearch()
        assert string_local_search.iterate_string(chromosome, statement, objective, 2, 1)
        assert statement.value == "tett"
