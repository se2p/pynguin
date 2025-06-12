#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

from pynguin.testcase.localsearchstatement import IntegerLocalSearch, StringLocalSearch
from pynguin.testcase.statement import IntPrimitiveStatement, FloatPrimitiveStatement, StringPrimitiveStatement


def test_iterate_success(monkeypatch, result) -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 3 + [False]

    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective,1,2)

def test_iterate_fail(monkeypatch, result) -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]

    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective,1,2) is False

@pytest.mark.parametrize(
    "value, delta, increasing_factor, iterations, final_result",
    [
        (2, 1, 2, 5, 33),
        (39, 4, 23, 3, 2251),
        (128, 0, 3, 10, 128)
    ]
)
def test_iterate_int_value(monkeypatch, result,value, delta, increasing_factor, iterations, final_result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * iterations + [False]
    statement = IntPrimitiveStatement(chromosome, value)
    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, delta, increasing_factor)
    assert statement.value == final_result

def test_iterate_float_value(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 3 + [False]
    statement = FloatPrimitiveStatement(chromosome, 2.56)
    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, 1.5, 1.5)
    assert statement.value == 9.685

def test_apply_random_mutations_fail(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = 0

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective) is False

def test_apply_random_mutations_success(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [1]

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective)

def test_apply_random_mutations_negative_success(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = -1

    local_search = StringLocalSearch()
    assert local_search.apply_random_mutations(chromosome, 4, objective)


def test_apply_random_mutations_improves(monkeypatch, result) -> None:
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

def test_apply_random_mutations_worsens(monkeypatch, result) -> None:
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

def test_remove_chars(monkeypatch, result) -> None:
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

def test_remove_chars2(monkeypatch, result) -> None:
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

def test_remove_chars_all(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True]*20

    statement = StringPrimitiveStatement(chromosome, "test")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch()
    local_search.remove_chars(chromosome, 4, objective)
    assert statement.value == ""

def test_remove_chars_none(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]*20

    statement = StringPrimitiveStatement(chromosome, "This should stay")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch()
    local_search.remove_chars(chromosome, 4, objective)
    assert statement.value == "This should stay"
