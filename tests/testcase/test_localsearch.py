#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

from pynguin.testcase.localsearchstatement import IntegerLocalSearch
from pynguin.testcase.statement import IntPrimitiveStatement, FloatPrimitiveStatement


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

def test_iterate_int_value(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 3 + [False]
    statement = IntPrimitiveStatement(chromosome, 2)
    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, 1, 2)
    assert statement.value == 9

def test_iterate_int_value2(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 7 + [False]
    statement = IntPrimitiveStatement(chromosome, 5)
    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, 2, 3)
    assert statement.value == 2191

def test_iterate_float_value(monkeypatch, result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 3 + [False]
    statement = FloatPrimitiveStatement(chromosome, 2.56)
    local_search = IntegerLocalSearch()
    assert local_search.iterate(chromosome, statement, objective, 1.5, 1.5)
    assert statement.value == 9.685


