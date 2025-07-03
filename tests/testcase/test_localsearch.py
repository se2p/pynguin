#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import enum
import sys

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from pynguin.analyses.typesystem import TypeInfo
from pynguin.testcase.localsearchstatement import BooleanLocalSearch
from pynguin.testcase.localsearchstatement import BytesLocalSearch
from pynguin.testcase.localsearchstatement import ComplexLocalSearch
from pynguin.testcase.localsearchstatement import EnumLocalSearch
from pynguin.testcase.localsearchstatement import FloatLocalSearch
from pynguin.testcase.localsearchstatement import IntegerLocalSearch
from pynguin.testcase.localsearchstatement import StringLocalSearch
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import BooleanPrimitiveStatement
from pynguin.testcase.statement import BytesPrimitiveStatement
from pynguin.testcase.statement import ComplexPrimitiveStatement
from pynguin.testcase.statement import EnumPrimitiveStatement
from pynguin.testcase.statement import FloatPrimitiveStatement
from pynguin.testcase.statement import IntPrimitiveStatement
from pynguin.testcase.statement import StringPrimitiveStatement
from pynguin.utils.generic.genericaccessibleobject import GenericEnum


@pytest.fixture(autouse=True)
def setup_timer():
    timer = LocalSearchTimer.get_instance()
    timer.limit_reached = MagicMock(return_value=False)


@pytest.mark.parametrize(
    "value, result, return_value",
    [
        (True, False, True),
        (True, True, False),
        (False, True, True),
        (False, False, False),
    ],
)
def test_bool_local_search(value, result, return_value) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.return_value = return_value
    statement = BooleanPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = BooleanLocalSearch(chromosome, 1, objective)
    local_search.search()
    assert statement.value == result


class Number(enum.Enum):
    NONE = 0
    ONE = 1
    TWO = 2
    THREE = 3
    FOUR = 4


@pytest.mark.parametrize(
    "value, side_effect",
    [
        (Number.THREE, [True]),
        (Number.THREE, [False, True]),
        (Number.TWO, [False] * 2 + [True]),
    ],
)
def test_enum_local_search(value, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    generic = GenericEnum(TypeInfo(Number))
    statement = EnumPrimitiveStatement(chromosome, generic)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement

    local_search = EnumLocalSearch(chromosome, 1, objective)
    local_search.search()
    assert statement.value != value


def test_iterate_success() -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()

    objective.has_improved.side_effect = [True] * 3 + [False]

    local_search = IntegerLocalSearch(chromosome, 1, objective)
    assert local_search.iterate(statement, 1, 2)


def test_iterate_fail() -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]

    local_search = IntegerLocalSearch(chromosome, 1, objective)
    assert local_search.iterate(statement, 1, 2) is False


@pytest.mark.parametrize(
    "value, delta, increasing_factor, iterations, final_result",
    [(2, 1, 2, 5, 33), (39, 4, 23, 3, 2251), (128, 0, 3, 10, 128)],
)
def test_iterate_int_value(value, delta, increasing_factor, iterations, final_result) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * iterations + [False]
    statement = IntPrimitiveStatement(chromosome, value)
    local_search = IntegerLocalSearch(chromosome, 1, objective)
    assert local_search.iterate(statement, delta, increasing_factor)
    assert statement.value == final_result


def test_iterate_float_value() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 3 + [False]
    statement = FloatPrimitiveStatement(chromosome, 2.56)
    local_search = IntegerLocalSearch(chromosome, 1, objective)
    assert local_search.iterate(statement, 1.5, 1.5)
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
    local_search = IntegerLocalSearch(chromosome, 2, objective)
    local_search.search()
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
    local_search = FloatLocalSearch(chromosome, 1, objective)
    local_search.search()
    assert statement.value == result


@pytest.mark.parametrize(
    "value, result, objective_effect",
    [
        (complex(1.0, 1.0), complex(1.0, 1.0), [False] * 100),
        (complex(1.0, 1.0), complex(2.0, 1.0), [True] + [False] * 100),
        (complex(1.0, 1.0), complex(1.0, 4.0), [False] * 32 + [True] * 2 + [False] * 100),
        (complex(1.0, 1.0), complex(1.3, 1.0), [False] * 2 + [True] * 2 + [False] * 100),
        (
            complex(1.0, 1.0),
            complex(8.0, 2.7),
            [True] * 3 + [False] * 33 + [True] + [False] * 3 + [True] * 3 + [False] * 100,
        ),
        (
            complex(1.0, 1.0),
            complex(7.0, 0.0),
            [True] * 3 + [False] * 2 + [True] + [False] * 34 + [True] + [False] * 100,
        ),
    ],
)
def test_complex_search(value, result, objective_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = objective_effect
    objective.has_changed.return_value = 0
    statement = ComplexPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = ComplexLocalSearch(chromosome, 1, objective)
    local_search.search()
    assert statement.value.real == result.real
    assert statement.value.imag == result.imag


def test_apply_random_mutations_fail() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = 0

    local_search = StringLocalSearch(chromosome, 4, objective)
    assert local_search.apply_random_mutations() is False


def test_apply_random_mutations_success() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [1]

    local_search = StringLocalSearch(chromosome, 4, objective)
    assert local_search.apply_random_mutations()


def test_apply_random_mutations_negative_success() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = -1

    local_search = StringLocalSearch(chromosome, 4, objective)
    assert local_search.apply_random_mutations()


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

    local_search = StringLocalSearch(chromosome, 4, objective)
    assert local_search.apply_random_mutations()
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

    local_search = StringLocalSearch(chromosome, 4, objective)
    assert local_search.apply_random_mutations()
    assert statement.value == "testString"


def test_remove_chars() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False] + [True] + [False] * 10

    statement = StringPrimitiveStatement(chromosome, "testString")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch(chromosome, 4, objective)
    local_search.remove_chars()
    assert statement.value == "testStrig"


def test_remove_chars2() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False] + [True] * 2 + [False] * 10

    statement = StringPrimitiveStatement(chromosome, "testing")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch(chromosome, 4, objective)
    local_search.remove_chars()
    assert statement.value == "testg"


def test_remove_chars_all() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 20

    statement = StringPrimitiveStatement(chromosome, "test")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch(chromosome, 4, objective)
    local_search.remove_chars()
    assert statement.value == ""  # noqa: PLC1901


def test_remove_chars_none() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False] * 20

    statement = StringPrimitiveStatement(chromosome, "This should stay")
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(5)]
    chromosome.test_case.statements[4] = statement

    local_search = StringLocalSearch(chromosome, 4, objective)
    local_search.remove_chars()
    assert statement.value == "This should stay"


@pytest.mark.parametrize(
    "value, result, side_effect",
    [
        (
            "Helo",
            "Hello",
            [False] * 3 + [True] * 5 + [False] + [True] * 3 + [False] + [True] * 2 + [False] * 20,
        ),
        ("Helo", "Heloaa", [False] * 4 + [True] + [False] * 2 + [True] + [False] * 10),
        (
            "Hello",
            "\x00Hello",
            [True]
            + [False]
            + [True] * 6
            + [False]
            + [True] * 5
            + [False]
            + [True] * 2
            + [False] * 100,
        ),
    ],
)
def test_string_add(value, result, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = StringPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = StringLocalSearch(chromosome, 1, objective)
    local_search.add_chars()
    assert statement.value == result


@pytest.mark.parametrize(
    "value, result, side_effect",
    [
        ("Helfo", "Hello", [False] * 2 + [True] * 2 + [False] * 2 + [True] * 2 + [False] * 100),
        ("Hello", "Aello", [False] * 9 + [True] * 3 + [False] * 100),
        ("Hello", "Hello", [False] * 10),
    ],
)
def test_replace_chars(value, result, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = StringPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(4)]
    chromosome.test_case.statements[1] = statement
    local_search = StringLocalSearch(chromosome, 1, objective)
    local_search.replace_chars()
    assert statement.value == result


def test_iterate_string_fail() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]
    statement = StringPrimitiveStatement(chromosome, "test")

    string_local_search = StringLocalSearch(chromosome, 1, objective)
    assert not string_local_search.iterate_string(statement, 3, 2)


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

    string_local_search = StringLocalSearch(chromosome, 1, objective)
    assert string_local_search.iterate_string(statement, char_position, delta)
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

    string_local_search = StringLocalSearch(chromosome, 1, objective)
    assert string_local_search.iterate_string(statement, 0, 1)
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

    string_local_search = StringLocalSearch(chromosome, 1, objective)
    assert not string_local_search.iterate_string(statement, 0, delta)
    assert statement.value == "test"


def test_iterate_string_lower_bound_second_iteration() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, chr(1))
    objective.has_improved.side_effect = [True] * 10 + [False]

    string_local_search = StringLocalSearch(chromosome, 1, objective)
    assert string_local_search.iterate_string(statement, 0, -1)
    assert statement.value == chr(0)


def test_iterate_string_upper_bound_second_iteration() -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, chr(sys.maxunicode - 1))
    objective.has_improved.side_effect = [True] * 10 + [False]

    string_local_search = StringLocalSearch(chromosome, 1, objective)
    assert string_local_search.iterate_string(statement, 0, 1)
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

        string_local_search = StringLocalSearch(chromosome, 1, objective)
        assert string_local_search.iterate_string(statement, 2, 1)
        assert statement.value == "tett"


@pytest.mark.parametrize(
    "value, result, side_effect",
    [
        (b"Hello", b"Helo", [False] * 2 + [True] + [False] * 2),
        (b"test", b"tes", [True] + [False] * 3),
        (b"test", b"test", [False] * 4),
        (b"test", b"", [True] * 4),
        (b"Hello", b"e", [True] * 3 + [False] + [True]),
    ],
)
def test_remove_bytes(value, result, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = BytesPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(3)]
    chromosome.test_case.statements[1] = statement
    local_search = BytesLocalSearch(chromosome, 1, objective)
    local_search.remove_values()
    assert statement.value == result


@pytest.mark.parametrize(
    "value, result, side_effect",
    [
        (
            b"Helo",
            b"Hello",
            [False] * 3 + [True] * 5 + [False] + [True] * 3 + [False] + [True] * 2 + [False] * 20,
        ),
        (b"Helo", b"Heloaa", [False] * 4 + [True] + [False] * 2 + [True] + [False] * 10),
        (
            b"Hello",
            b"\x00Hello",
            [True]
            + [False]
            + [True] * 6
            + [False]
            + [True] * 5
            + [False]
            + [True] * 2
            + [False] * 100,
        ),
    ],
)
def test_add_bytes(value, result, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = BytesPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = BytesLocalSearch(chromosome, 1, objective)
    local_search.add_values()
    assert statement.value == result


@pytest.mark.parametrize(
    "value, result, side_effect",
    [
        (b"Helfo", b"Hello", [False] * 2 + [True] * 2 + [False] * 2 + [True] * 2 + [False] * 100),
        (b"Hello", b"Aello", [False] * 9 + [True] * 3 + [False] * 100),
        (b"Hello", b"Hello", [False] * 10),
    ],
)
def test_replace_bytes(value, result, side_effect) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = BytesPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(4)]
    chromosome.test_case.statements[1] = statement
    local_search = BytesLocalSearch(chromosome, 1, objective)
    local_search.replace_values()
    assert statement.value == result


def test_bytes_random_mutation_fail() -> None:
    value = b"Hello"
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = 0
    statement = BytesPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = BytesLocalSearch(chromosome, 1, objective)
    assert not local_search._apply_random_mutations()
    assert statement.value == value


def test_bytes_random_mutation() -> None:
    value = b"Hello"
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [-1]
    statement = BytesPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(2)]
    chromosome.test_case.statements[1] = statement
    local_search = BytesLocalSearch(chromosome, 1, objective)
    assert local_search._apply_random_mutations()
    assert statement.value == value


def test_bytes_random_mutation_better_value() -> None:
    value = b"Hello"
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [1]
    statement = BytesPrimitiveStatement(chromosome, value)
    chromosome.test_case = MagicMock()
    chromosome.test_case.statements = [MagicMock() for _ in range(3)]
    chromosome.test_case.statements[1] = statement
    local_search = BytesLocalSearch(chromosome, 1, objective)
    assert local_search._apply_random_mutations()
