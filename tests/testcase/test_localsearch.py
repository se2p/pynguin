#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import enum
import math
import sys

from types import NoneType
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.analyses.typesystem import ANY
from pynguin.analyses.typesystem import TypeInfo
from pynguin.testcase.llmlocalsearch import LLMLocalSearch
from pynguin.testcase.localsearch import TestCaseLocalSearch
from pynguin.testcase.localsearchstatement import BooleanLocalSearch
from pynguin.testcase.localsearchstatement import BytesLocalSearch
from pynguin.testcase.localsearchstatement import ComplexLocalSearch
from pynguin.testcase.localsearchstatement import DictStatementLocalSearch
from pynguin.testcase.localsearchstatement import EnumLocalSearch
from pynguin.testcase.localsearchstatement import FieldStatementLocalSearch
from pynguin.testcase.localsearchstatement import FloatLocalSearch
from pynguin.testcase.localsearchstatement import IntegerLocalSearch
from pynguin.testcase.localsearchstatement import NonDictCollectionLocalSearch
from pynguin.testcase.localsearchstatement import ParametrizedStatementLocalSearch
from pynguin.testcase.localsearchstatement import StringLocalSearch
from pynguin.testcase.localsearchstatement import choose_local_search_statement
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import BooleanPrimitiveStatement
from pynguin.testcase.statement import BytesPrimitiveStatement
from pynguin.testcase.statement import ComplexPrimitiveStatement
from pynguin.testcase.statement import ConstructorStatement
from pynguin.testcase.statement import DictStatement
from pynguin.testcase.statement import EnumPrimitiveStatement
from pynguin.testcase.statement import FieldStatement
from pynguin.testcase.statement import FloatPrimitiveStatement
from pynguin.testcase.statement import FunctionStatement
from pynguin.testcase.statement import IntPrimitiveStatement
from pynguin.testcase.statement import ListStatement
from pynguin.testcase.statement import MethodStatement
from pynguin.testcase.statement import NoneStatement
from pynguin.testcase.statement import ParametrizedStatement
from pynguin.testcase.statement import SetStatement
from pynguin.testcase.statement import StringPrimitiveStatement
from pynguin.testcase.statement import TupleStatement
from pynguin.testcase.statement import UIntPrimitiveStatement
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import GenericEnum
from pynguin.utils.mirror import Mirror
from pynguin.utils.report import CoverageEntry
from pynguin.utils.report import LineAnnotation


@pytest.fixture(autouse=True)
def setup_timer():
    timer = LocalSearchTimer()
    timer.limit_reached = MagicMock(return_value=False)


@pytest.fixture
def timer():
    timer = LocalSearchTimer()
    timer.limit_reached = MagicMock(return_value=False)
    return timer


@pytest.fixture
def tc_mock(default_test_case):
    test_case = MagicMock()
    tc_mock.test_case = default_test_case
    statements = [MagicMock() for _ in range(3)]
    test_case.test_case.statements = statements
    return test_case


def ls_test_case():
    test_case = MagicMock()
    statements = [MagicMock() for _ in range(3)]
    test_case.statements = statements
    return test_case


ls_tc = ls_test_case()


@pytest.mark.parametrize(
    "value, result, return_value",
    [
        (True, False, True),
        (True, True, False),
        (False, True, True),
        (False, False, False),
    ],
)
def test_bool_local_search(value, result, return_value, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.return_value = return_value
    statement = BooleanPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = BooleanLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
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
def test_enum_local_search(value, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    generic = GenericEnum(TypeInfo(Number))
    statement = EnumPrimitiveStatement(tc_mock, generic)
    tc_mock.test_case.statements[1] = statement

    local_search = EnumLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    local_search.search()
    assert statement.value != value


def test_iterate_success(timer) -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()

    objective.has_improved.side_effect = [True] * 3 + [False]

    local_search = IntegerLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search.iterate(statement, 1, 2)


def test_iterate_fail(timer) -> None:
    chromosome = MagicMock()
    statement = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]

    local_search = IntegerLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search.iterate(statement, 1, 2) is False


@pytest.mark.parametrize(
    "value, delta, increasing_factor, iterations, final_result",
    [(2, 1, 2, 5, 33), (39, 4, 23, 3, 2251), (128, 0, 3, 10, 128)],
)
def test_iterate_int_value(value, delta, increasing_factor, iterations, final_result, timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * iterations + [False]
    statement = IntPrimitiveStatement(chromosome, value)
    local_search = IntegerLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search.iterate(statement, delta, increasing_factor)
    assert statement.value == final_result


def test_iterate_float_value(timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 3 + [False]
    statement = FloatPrimitiveStatement(chromosome, 2.56)
    local_search = IntegerLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
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
def test_int_search(value, result, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = IntPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[2] = statement
    local_search = IntegerLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
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
def test_float_search(value, result, objective_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = objective_effect
    objective.has_changed.return_value = 0
    statement = FloatPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = FloatLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
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
def test_complex_search(value, result, objective_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = objective_effect
    objective.has_changed.return_value = 0
    statement = ComplexPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = ComplexLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    local_search.search()
    assert statement.value.real == result.real
    assert statement.value.imag == result.imag


def test_apply_random_mutations_fail(timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = 0

    local_search = StringLocalSearch(chromosome, 4, objective, TestFactory(MagicMock()), timer)
    assert local_search.apply_random_mutations() is False


def test_apply_random_mutations_success(timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [1]

    local_search = StringLocalSearch(chromosome, 4, objective, TestFactory(MagicMock()), timer)
    assert local_search.apply_random_mutations()


def test_apply_random_mutations_negative_success(timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_changed.return_value = -1

    local_search = StringLocalSearch(chromosome, 4, objective, TestFactory(MagicMock()), timer)
    assert local_search.apply_random_mutations()


def test_apply_random_mutations_improves(tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_changed.return_value = 1
    statement = StringPrimitiveStatement(tc_mock, "testString")

    def side_effect():
        statement.value = "String1"

    statement.randomize_value = MagicMock(side_effect=side_effect)

    tc_mock.test_case.statements[1] = statement
    statement.value = "testString"

    local_search = StringLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search.apply_random_mutations()
    assert statement.value == "String1"


def test_apply_random_mutations_worsens(tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_changed.return_value = -1
    statement = StringPrimitiveStatement(tc_mock, "testString")

    def side_effect():
        statement.value = "String1"

    statement.randomize_value = MagicMock(side_effect=side_effect)
    tc_mock.test_case.statements[0] = statement
    statement.value = "testString"

    local_search = StringLocalSearch(tc_mock, 0, objective, TestFactory(MagicMock()), timer)
    assert local_search.apply_random_mutations()
    assert statement.value == "testString"


def test_remove_chars(tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = [False] + [True] + [False] * 10

    statement = StringPrimitiveStatement(tc_mock, "testString")
    tc_mock.test_case.statements[2] = statement

    local_search = StringLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    local_search.remove_chars()
    assert statement.value == "testStrig"


def test_remove_chars2(tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = [False] + [True] * 2 + [False] * 10

    statement = StringPrimitiveStatement(tc_mock, "testing")
    tc_mock.test_case.statements[2] = statement

    local_search = StringLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    local_search.remove_chars()
    assert statement.value == "testg"


def test_remove_chars_all(tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 20

    statement = StringPrimitiveStatement(tc_mock, "test")
    tc_mock.test_case.statements[2] = statement

    local_search = StringLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    local_search.remove_chars()
    assert statement.value == ""  # noqa: PLC1901


def test_remove_chars_none(tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = [False] * 20

    statement = StringPrimitiveStatement(tc_mock, "This should stay")
    tc_mock.test_case.statements[2] = statement

    local_search = StringLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
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
def test_string_add(value, result, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = StringPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = StringLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
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
def test_replace_chars(value, result, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = StringPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = StringLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    local_search.replace_chars()
    assert statement.value == result


def test_iterate_string_fail(timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    objective.has_improved.side_effect = [False]
    statement = StringPrimitiveStatement(chromosome, "test")

    string_local_search = StringLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
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
def test_iterate_string(value, result, delta, char_position, timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, value)
    objective.has_improved.side_effect = [True, False]

    string_local_search = StringLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert string_local_search.iterate_string(statement, char_position, delta)
    assert statement.value == result


@pytest.mark.parametrize(
    "value, result, side_effect",
    [("test", "west", [True] * 2 + [False]), ("test", "{est", [True] * 3 + [False])],
)
def test_iterate_string_multiple_iterations(value, result, side_effect, timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, value)
    objective.has_improved.side_effect = side_effect

    string_local_search = StringLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert string_local_search.iterate_string(statement, 0, 1)
    assert statement.value == result


@pytest.mark.parametrize(
    "delta",
    [(-1000000), 10000000],
)
def test_iterate_string_bounds(delta, timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, "test")
    objective.has_improved.side_effect = [True, False]

    string_local_search = StringLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert not string_local_search.iterate_string(statement, 0, delta)
    assert statement.value == "test"


def test_iterate_string_lower_bound_second_iteration(timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, chr(1))
    objective.has_improved.side_effect = [True] * 10 + [False]

    string_local_search = StringLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert string_local_search.iterate_string(statement, 0, -1)
    assert statement.value == chr(0)


def test_iterate_string_upper_bound_second_iteration(timer) -> None:
    chromosome = MagicMock()
    objective = MagicMock()
    statement = StringPrimitiveStatement(chromosome, chr(sys.maxunicode - 1))
    objective.has_improved.side_effect = [True] * 10 + [False]

    string_local_search = StringLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
    assert string_local_search.iterate_string(statement, 0, 1)
    assert statement.value == chr(sys.maxunicode)


def test_iterate_string_timer() -> None:
        config.configuration.local_search.local_search_time = -1000000
        chromosome = MagicMock()
        objective = MagicMock()
        objective.has_improved.side_effect = [True] * 10 + [False]
        statement = StringPrimitiveStatement(chromosome, "test")
        timer = LocalSearchTimer()
        timer.start_timer()

        string_local_search = StringLocalSearch(chromosome, 1, objective, TestFactory(MagicMock()), timer)
        assert string_local_search.iterate_string(statement, 2, 1)
        assert statement.value == "tett"


def test_string_local_search(monkeypatch, timer):
    objective = MagicMock()
    objective.has_improved.return_value = True
    string_local_search = StringLocalSearch(MagicMock(), 1, MagicMock(), TestFactory(MagicMock()), timer)
    monkeypatch.setattr(StringLocalSearch, "apply_random_mutations", lambda *_, **__: True)
    monkeypatch.setattr(StringLocalSearch, "remove_chars", lambda *_, **__: True)
    monkeypatch.setattr(StringLocalSearch, "replace_chars", lambda *_, **__: True)
    monkeypatch.setattr(StringLocalSearch, "add_chars", lambda *_, **__: True)

    assert string_local_search.search()


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
def test_remove_bytes(value, result, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = BytesPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = BytesLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
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
def test_add_bytes(value, result, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = BytesPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = BytesLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
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
def test_replace_bytes(value, result, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    statement = BytesPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = BytesLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    local_search.replace_values()
    assert statement.value == result


def test_bytes_random_mutation_fail(tc_mock, timer) -> None:
    value = b"Hello"
    objective = MagicMock()
    objective.has_changed.return_value = 0
    statement = BytesPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[2] = statement
    local_search = BytesLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert not local_search._apply_random_mutations()
    assert statement.value == value


def test_bytes_random_mutation(tc_mock, timer) -> None:
    value = b"Hello"
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [-1]
    statement = BytesPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = BytesLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search._apply_random_mutations()
    assert statement.value == value


def test_bytes_random_mutation_better_value(tc_mock, timer) -> None:
    value = b"Hello"
    objective = MagicMock()
    objective.has_changed.side_effect = [0] * 3 + [1]
    statement = BytesPrimitiveStatement(tc_mock, value)
    tc_mock.test_case.statements[1] = statement
    local_search = BytesLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search._apply_random_mutations()


def test_bytes_local_search(monkeypatch, timer):
    objective = MagicMock()
    objective.has_improved.return_value = True
    bytes_local_search = BytesLocalSearch(MagicMock(), 1, MagicMock(), TestFactory(MagicMock()), timer)
    monkeypatch.setattr(BytesLocalSearch, "_apply_random_mutations", lambda *_, **__: True)
    monkeypatch.setattr(BytesLocalSearch, "remove_values", lambda *_, **__: True)
    monkeypatch.setattr(BytesLocalSearch, "replace_values", lambda *_, **__: True)
    monkeypatch.setattr(BytesLocalSearch, "add_values", lambda *_, **__: True)

    assert bytes_local_search.search()


@pytest.mark.parametrize(
    "result1, result2, side_effect",
    [
        (True, 1, [True, False]),
        (False, 2, [False, False]),
        (True, 0, [True, True]),
    ],
)
def test_non_dict_remove_list(result1, result2, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = ListStatement(
        tc_mock,
        int_statement.ret_val.type,
        [int_statement.ret_val, int_statement_2.ret_val],
    )
    local_search = NonDictCollectionLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search.remove_entries(statement) == result1
    assert len(statement.elements) == result2


@pytest.mark.parametrize(
    "result1, result2, side_effect",
    [
        (True, 1, [True, False]),
        (False, 2, [False, False]),
        (True, 0, [True, True]),
    ],
)
def test_non_dict_remove_tuple(result1, result2, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = TupleStatement(
        tc_mock,
        int_statement.ret_val.type,
        [int_statement.ret_val, int_statement_2.ret_val],
    )
    local_search = NonDictCollectionLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search.remove_entries(statement) == result1
    assert len(statement.elements) == result2


@pytest.mark.parametrize(
    "result1, result2, side_effect",
    [
        (True, 2, [True, False, False]),
        (False, 3, [False, False, False]),
        (True, 0, [True, True, True]),
        (True, 1, [True, False, True]),
    ],
)
def test_non_dict_remove_set(result1, result2, side_effect, tc_mock, timer) -> None:
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    int_statement_3 = IntPrimitiveStatement(tc_mock, 17)

    statement = SetStatement(
        tc_mock,
        int_statement.ret_val.type,
        [int_statement.ret_val, int_statement_2.ret_val, int_statement_3.ret_val],
    )
    tc_mock.test_case.statements[2] = statement
    local_search = NonDictCollectionLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert local_search.remove_entries(statement) == result1
    assert len(statement.elements) == result2


@pytest.mark.parametrize(
    "result1, result2, side_effect",
    [
        (True, 2, [True, False, False]),
        (True, 5, [True] * 4 + [False] * 2),
        (False, 1, [False] * 2),
    ],
)
def test_non_dict_add_list(result1, result2, side_effect, tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = ListStatement(tc_mock, int_statement.ret_val.type, [int_statement.ret_val])
    tc_mock.test_case.get_objects.return_value = [int_statement_2.ret_val, int_statement.ret_val]
    local_search = NonDictCollectionLocalSearch(tc_mock, 3, objective, TestFactory(MagicMock()), timer)
    assert local_search.add_entries(statement) == result1
    assert len(statement.elements) == result2


@pytest.mark.parametrize(
    "result1, result2, side_effect",
    [
        (True, 2, [True, False, False]),
        (True, 5, [True] * 4 + [False] * 2),
        (False, 1, [False] * 2),
    ],
)
def test_non_dict_add_tuple(result1, result2, side_effect, tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = TupleStatement(tc_mock, int_statement.ret_val.type, [int_statement.ret_val])
    tc_mock.test_case.get_objects.return_value = [int_statement_2, int_statement]
    local_search = NonDictCollectionLocalSearch(tc_mock, 1, objective, TestFactory(MagicMock()), timer)
    assert local_search.add_entries(statement) == result1
    assert len(statement.elements) == result2


@pytest.mark.parametrize(
    "result1, result2, side_effect",
    [
        (True, 2, [True, False]),
        (True, 2, [True] * 4 + [False]),
        (False, 1, [False] * 2),
    ],
)
def test_non_dict_add_set(result1, result2, side_effect, tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)

    statement = SetStatement(tc_mock, int_statement.ret_val.type, [int_statement.ret_val])
    tc_mock.test_case.get_objects.return_value = [int_statement_2.ret_val, int_statement.ret_val]
    tc_mock.test_case.statements[2] = statement
    factory = MagicMock()
    factory.create_fitting_reference.return_value = None
    local_search = NonDictCollectionLocalSearch(tc_mock, 2, objective, factory, timer)
    assert local_search.add_entries(statement) == result1
    assert len(statement.elements) == result2


def test_non_dict_add_set2(tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = [True, False, False]
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    int_statement_3 = IntPrimitiveStatement(tc_mock, 17)
    statement = SetStatement(tc_mock, int_statement.ret_val.type, [int_statement.ret_val])
    tc_mock.test_case.get_objects.return_value = [int_statement_2.ret_val, int_statement.ret_val]
    factory = MagicMock()
    local_search = NonDictCollectionLocalSearch(tc_mock, 2, objective, factory, timer)
    assert local_search.add_entries(statement)
    assert len(statement.elements) == 2
    assert (
        int_statement_3.ret_val in statement.elements
        or int_statement_2.ret_val in statement.elements
    )
    assert not (
        int_statement_3.ret_val in statement.elements
        and int_statement_2.ret_val in statement.elements
    )


@pytest.mark.parametrize(
    "result1, pos_element, pos_list, side_effect",
    [
        (True, 0, 1, [True, False]),
        (True, 1, 0, [True] * 4 + [False]),
        (False, 0, 0, [False] * 2),
    ],
)
def test_non_dict_replace_list(result1, pos_element, pos_list, side_effect, tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    list_statement = [int_statement, int_statement_2]
    statement = ListStatement(
        tc_mock,
        int_statement.ret_val.type,
        [int_statement.ret_val, int_statement_2.ret_val],
    )
    tc_mock.test_case.get_objects.return_value = [int_statement_2.ret_val, int_statement.ret_val]
    local_search = NonDictCollectionLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert local_search.replace_entries(statement) == result1
    assert len(statement.elements) == 2
    assert statement.elements[pos_element] == list_statement[pos_list].ret_val


@pytest.mark.parametrize(
    "result1, pos_element, pos_list, side_effect",
    [
        (True, 0, 1, [True, False]),
        (True, 1, 0, [True] * 4 + [False]),
        (False, 0, 0, [False] * 2),
    ],
)
def test_non_dict_replace_tuple(result1, pos_element, pos_list, side_effect, tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    list_statement = [int_statement, int_statement_2]
    statement = TupleStatement(
        tc_mock,
        int_statement.ret_val.type,
        [int_statement.ret_val, int_statement_2.ret_val],
    )
    tc_mock.test_case.get_objects.return_value = [int_statement_2.ret_val, int_statement.ret_val]
    tc_mock.test_case.statements[0] = statement
    local_search = NonDictCollectionLocalSearch(tc_mock, 0, objective, TestFactory(MagicMock()), timer)
    assert local_search.replace_entries(statement) == result1
    assert len(statement.elements) == 2
    assert statement.elements[pos_element] == list_statement[pos_list].ret_val


def test_non_dict_replace_set(tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 2 + [False]
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    int_statement_3 = IntPrimitiveStatement(tc_mock, 17)
    statement = SetStatement(
        tc_mock,
        int_statement.ret_val.type,
        [int_statement.ret_val, int_statement_2.ret_val],
    )
    tc_mock.test_case.get_objects.return_value = [
        int_statement_2.ret_val,
        int_statement.ret_val,
        int_statement_3.ret_val,
    ]
    local_search = NonDictCollectionLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert local_search.replace_entries(statement)
    assert len(statement.elements) == 2
    assert statement.elements[0] == int_statement_3.ret_val
    assert statement.elements[1] == int_statement.ret_val


def test_non_dict_local_search(monkeypatch, timer):
    objective = MagicMock()
    objective.has_improved.return_value = True
    non_dict_local_search = NonDictCollectionLocalSearch(
        MagicMock(), 1, MagicMock(), TestFactory(MagicMock()), timer
    )
    monkeypatch.setattr(NonDictCollectionLocalSearch, "remove_entries", lambda *_, **__: True)
    monkeypatch.setattr(NonDictCollectionLocalSearch, "replace_entries", lambda *_, **__: True)
    monkeypatch.setattr(NonDictCollectionLocalSearch, "add_entries", lambda *_, **__: True)

    assert non_dict_local_search.search()


def test_dict_local_search(monkeypatch, timer):
    objective = MagicMock()
    objective.has_improved.return_value = True
    dict_local_search = DictStatementLocalSearch(
        MagicMock(), 1, MagicMock(), TestFactory(MagicMock()), timer
    )
    monkeypatch.setattr(DictStatementLocalSearch, "remove_entries", lambda *_, **__: True)
    monkeypatch.setattr(DictStatementLocalSearch, "replace_entries", lambda *_, **__: True)
    monkeypatch.setattr(DictStatementLocalSearch, "add_entries", lambda *_, **__: True)

    assert dict_local_search.search()


@pytest.mark.parametrize(
    "result, size, side_effect",
    [
        (True, 1, [True, False, True]),
        (True, 2, [False, False, True]),
        (False, 3, [False] * 3),
        (True, 0, [True] * 3),
    ],
)
def test_dict_remove(tc_mock, result, size, side_effect, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    int_statement_3 = IntPrimitiveStatement(tc_mock, 17)
    statement = DictStatement(
        tc_mock,
        ANY,
        [
            (int_statement.ret_val, int_statement_2.ret_val),
            (int_statement_3.ret_val, int_statement_2.ret_val),
            (int_statement_2.ret_val, int_statement_3),
        ],
    )
    local_search = DictStatementLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert local_search.remove_entries(statement) == result
    assert len(statement.elements) == size


@pytest.mark.parametrize(
    "result, size, side_effect",
    [
        (True, 2, [False] + [True] + [False] * 10),
        (True, 3, [False] + [True] * 2 + [False] * 10),
        (False, 1, [False] * 11),
    ],
)
def test_dict_add(tc_mock, result, size, side_effect, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = side_effect
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    int_statement_3 = IntPrimitiveStatement(tc_mock, 17)
    statement = DictStatement(
        tc_mock,
        ANY,
        [
            (int_statement.ret_val, int_statement_2.ret_val),
        ],
    )
    tc_mock.test_case.get_objects.return_value = [int_statement_2, int_statement, int_statement_3]
    local_search = DictStatementLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert local_search.add_entries(statement) == result
    assert len(statement.elements) == size


def test_dict_add_missing_key(tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = [False] * 20
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = DictStatement(tc_mock, ANY, [(int_statement.ret_val, int_statement_2.ret_val)])
    tc_mock.test_case.get_objects.return_value = [int_statement]
    local_search = DictStatementLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert not local_search.add_entries(statement)
    assert len(statement.elements) == 1


def test_dict_replace(tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.side_effect = [True] * 10
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = DictStatement(
        tc_mock,
        ANY,
        [
            (int_statement.ret_val, int_statement_2.ret_val),
        ],
    )
    tc_mock.test_case.get_objects.side_effect = (
        [*[int_statement.ret_val]],
        *[[int_statement_2.ret_val, int_statement.ret_val]],
    )
    local_search = DictStatementLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert local_search.replace_entries(statement)
    assert statement.elements[0] == (int_statement_2.ret_val, int_statement.ret_val)
    assert len(statement.elements) == 1


def test_dict_replace_max_insertions(tc_mock, monkeypatch, timer):
    monkeypatch.setattr("pynguin.config.LocalSearchConfiguration.ls_dict_max_insertions", 10)
    objective = MagicMock()
    objective.has_improved.side_effect = [False] * 30
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = DictStatement(
        tc_mock,
        ANY,
        [
            (int_statement.ret_val, int_statement_2.ret_val),
        ],
    )
    tc_mock.test_case.get_objects.side_effect = [
        *[[int_statement.ret_val] * 11],
        *[[int_statement_2, int_statement.ret_val] * 11],
    ]
    local_search = DictStatementLocalSearch(tc_mock, 2, objective, TestFactory(MagicMock()), timer)
    assert statement.elements[0] == (int_statement.ret_val, int_statement_2.ret_val)

    assert not local_search.replace_entries(statement)
    assert statement.elements[0] == (int_statement.ret_val, int_statement_2.ret_val)
    assert len(statement.elements) == 1


def test_fix_key_error(tc_mock, default_test_case, timer):
    tc_mock.test_case = default_test_case
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = DictStatement(
        tc_mock,
        ANY,
        [
            (int_statement.ret_val, int_statement_2.ret_val),
        ],
    )
    local_search = DictStatementLocalSearch(tc_mock, 0, MagicMock(), TestFactory(MagicMock()), timer)
    error = KeyError(23)
    execution_result = MagicMock
    tc_mock.get_last_execution_result = execution_result
    errors: dict = dict.fromkeys(range(3))
    execution_result.exceptions = errors
    execution_result.exceptions[0] = error
    default_test_case.statements.append(statement)

    assert local_search._fix_possible_key_error(statement)
    assert len(default_test_case.statements) == 2
    assert default_test_case.statements[1] == statement
    assert default_test_case.statements[0].value == 23


def test_fix_key_error_no_key_error(tc_mock, default_test_case, timer):
    tc_mock.test_case = default_test_case
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = DictStatement(
        tc_mock,
        ANY,
        [
            (int_statement.ret_val, int_statement_2.ret_val),
        ],
    )
    execution_result = MagicMock
    tc_mock.get_last_execution_result = execution_result
    errors: dict = dict.fromkeys(range(3))
    execution_result.exceptions = errors
    local_search = DictStatementLocalSearch(tc_mock, 0, MagicMock(), TestFactory(MagicMock()), timer)
    assert not local_search._fix_possible_key_error(statement)


@pytest.mark.parametrize(
    "statement, correct_type",
    [
        (NoneStatement(ls_tc), ParametrizedStatementLocalSearch),
        (BooleanPrimitiveStatement(ls_tc, False), BooleanLocalSearch),  # noqa: FBT003
        (EnumPrimitiveStatement(ls_tc, GenericEnum(TypeInfo(Number))), EnumLocalSearch),
        (IntPrimitiveStatement(ls_tc, 42), IntegerLocalSearch),
        (UIntPrimitiveStatement(ls_tc, 24), IntegerLocalSearch),
        (FloatPrimitiveStatement(ls_tc, math.pi), FloatLocalSearch),
        (ComplexPrimitiveStatement(ls_tc, complex(43, 49.5)), ComplexLocalSearch),
        (StringPrimitiveStatement(ls_tc, "test"), StringLocalSearch),
        (BytesPrimitiveStatement(ls_tc, b"test"), BytesLocalSearch),
        (ListStatement(ls_tc, ANY, []), NonDictCollectionLocalSearch),
        (TupleStatement(ls_tc, ANY, []), NonDictCollectionLocalSearch),
        (SetStatement(ls_tc, ANY, []), NonDictCollectionLocalSearch),
        (DictStatement(ls_tc, ANY, []), DictStatementLocalSearch),
        (FunctionStatement(ls_tc, MagicMock()), ParametrizedStatementLocalSearch),
        (MethodStatement(ls_tc, MagicMock(), MagicMock()), ParametrizedStatementLocalSearch),
        (ConstructorStatement(ls_tc, MagicMock()), ParametrizedStatementLocalSearch),
        (FieldStatement(ls_tc, MagicMock(), MagicMock()), FieldStatementLocalSearch),
        (None, NoneType),
    ],
)
def test_choose_local_search_statement(statement, correct_type, tc_mock, timer) -> None:
    objective = MagicMock()
    tc_mock.test_case.statements[1] = statement
    assert type(choose_local_search_statement(tc_mock, 1, objective, MagicMock(), timer)) is correct_type


def test_llm_local_search_bool(monkeypatch, tc_mock, timer):
    config.configuration.local_search.local_search_llm = True
    config.configuration.local_search.local_search_same_datatype = False
    config.configuration.local_search.local_search_different_datatype = False
    values = iter([1.0, 0.0, 1.0])
    monkeypatch.setattr("pynguin.utils.randomness.next_float", lambda: next(values))
    objective = MagicMock()
    objective.has_improved.return_value = True
    local_search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    statement = BooleanPrimitiveStatement(tc_mock.test_case, False)  # noqa: FBT003
    tc_mock.test_case.statements[1] = statement
    local_search.local_search(tc_mock, MagicMock(), objective)
    assert statement.value


def test_local_search_no_methods(monkeypatch, tc_mock, timer):
    config.configuration.local_search.local_search_llm = False
    config.configuration.local_search.local_search_same_datatype = False
    config.configuration.local_search.local_search_different_datatype = False
    objective = MagicMock()
    objective.has_improved.return_value = True
    values = iter([0.0, 0.0, 0.0])
    monkeypatch.setattr("pynguin.utils.randomness.next_float", lambda: next(values))

    local_search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    statement = BooleanPrimitiveStatement(tc_mock.test_case, False)  # noqa: FBT003
    tc_mock.test_case.statements[1] = statement

    local_search.local_search(tc_mock, MagicMock(), objective)
    assert not statement.value


def test_local_search_no_selected_statement(monkeypatch, tc_mock, timer):
    config.configuration.local_search.local_search_llm = True
    config.configuration.local_search.local_search_primitives = False
    config.configuration.local_search.local_search_collections = False
    config.configuration.local_search.local_search_complex_objects = False

    values = iter([0.0, 0.0, 0.0])
    monkeypatch.setattr("pynguin.utils.randomness.next_float", lambda: next(values))
    local_search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    statement = BooleanPrimitiveStatement(tc_mock.test_case, False)  # noqa: FBT003
    tc_mock.test_case.statements[1] = statement
    objective = MagicMock()
    objective.has_improved.return_value = True
    local_search.local_search(tc_mock, MagicMock(), objective)
    assert not statement.value


def test_local_search_randomize_value(monkeypatch, tc_mock, timer):
    config.configuration.local_search.local_search_llm = False
    config.configuration.local_search.local_search_same_datatype = True
    config.configuration.local_search.local_search_different_datatype = False
    values = iter([1.0, 0.0, 1.0])
    monkeypatch.setattr("pynguin.utils.randomness.next_float", lambda: next(values))
    config.configuration.test_creation.string_length = 5
    local_search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    input_string = randomness.next_string(config.configuration.test_creation.string_length + 10)
    statement = StringPrimitiveStatement(tc_mock.test_case, input_string)
    statement.local_search_applied = True
    tc_mock.test_case.statements[1] = statement
    objective = MagicMock()
    objective.has_changed.return_value = 0
    local_search.local_search(tc_mock, MagicMock(), objective)
    assert statement.value != input_string


def test_llm_local_search_int(monkeypatch, tc_mock, timer):
    config.configuration.local_search.local_search_different_datatype = False
    config.configuration.local_search.local_search_llm = True
    config.configuration.local_search.local_search_same_datatype = False
    values = iter([1.0, 0.0, 1.0])
    monkeypatch.setattr("pynguin.utils.randomness.next_float", lambda: next(values))
    monkeypatch.setattr(
        "pynguin.testcase.llmlocalsearch.get_coverage_report",
        lambda *args, **kwargs: MagicMock(),  # noqa: ARG005
    )
    mock_llm_agent = MagicMock()
    monkeypatch.setattr(
        "pynguin.testcase.llmlocalsearch.LLMAgent", MagicMock(return_value=mock_llm_agent)
    )
    objective = MagicMock()
    objective.has_improved.return_value = True

    local_search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    statement = IntPrimitiveStatement(tc_mock.test_case, 30)
    tc_mock.test_case.statements[1] = statement

    local_search.local_search(tc_mock, MagicMock(), objective)
    assert statement.value == 30


def test_llm_local_search_int2(monkeypatch, tc_mock):
    monkeypatch.setattr(
        "pynguin.testcase.llmlocalsearch.get_coverage_report",
        lambda *args, **kwargs: MagicMock(),  # noqa: ARG005
    )
    mock_llm_agent = MagicMock()
    monkeypatch.setattr(
        "pynguin.testcase.llmlocalsearch.LLMAgent", MagicMock(return_value=mock_llm_agent)
    )
    monkeypatch.setattr("pynguin.testcase.llmlocalsearch.get_module_source_code", lambda: "")
    objective = MagicMock()
    objective.has_improved.return_value = True
    config.configuration.local_search.ls_llm_whole_module = True

    statement = IntPrimitiveStatement(tc_mock.test_case, 30)
    tc_mock.test_case.statements[1] = statement

    llm_local_search = LLMLocalSearch(tc_mock, objective, MagicMock(), MagicMock(), MagicMock())
    assert not llm_local_search.llm_local_search(1)


def test_local_search_different_fail(monkeypatch, tc_mock, timer):
    config.configuration.local_search.local_search_llm = False
    config.configuration.local_search.local_search_same_datatype = False
    config.configuration.local_search.local_search_different_datatype = True
    values = iter([1.0, 0.0, 1.0])
    monkeypatch.setattr("pynguin.utils.randomness.next_float", lambda: next(values))
    local_search = TestCaseLocalSearch(MagicMock(), MagicMock(), timer)
    statement = IntPrimitiveStatement(tc_mock.test_case, 30)
    tc_mock.test_case.statements[1] = statement
    tc_mock.test_case.clone.return_value = tc_mock.test_case
    objective = MagicMock()
    objective.has_improved.return_value = False
    local_search.local_search(tc_mock, MagicMock(), objective)
    assert type(tc_mock.test_case.statements[1]) is IntPrimitiveStatement
    assert tc_mock.test_case.statements[1] == statement


@pytest.mark.parametrize(
    "improvement, result, num_tcs", [(True, True, 1), (False, False, 1), (True, False, 2)]
)
def test_llm_local_search_complete(monkeypatch, tc_mock, improvement, result, num_tcs):  # noqa : PLR0914
    monkeypatch.setattr(
        "pynguin.testcase.llmlocalsearch.get_coverage_report",
        lambda *args, **kwargs: MagicMock(),  # noqa: ARG005
    )
    mock_llm_agent = MagicMock()
    monkeypatch.setattr(
        "pynguin.testcase.llmlocalsearch.LLMAgent", MagicMock(return_value=mock_llm_agent)
    )
    objective = MagicMock()
    objective.has_improved.return_value = improvement

    statement = IntPrimitiveStatement(tc_mock.test_case, 30)
    tc_mock.test_case.statements[1] = statement

    source_lines = [
        "def test_function(x):",
        "    if x==3:",
        "        return True",
        "    return False",
    ]

    chromosome = MagicMock()
    chromosome.test_case = MagicMock()
    statements2: list[any] = [MagicMock() for _ in range(3)]
    statement2 = IntPrimitiveStatement(chromosome.test_case, 40)
    statements2[1] = statement2
    chromosome.test_case.statements = statements2
    chromosomes = [chromosome for _ in range(num_tcs)]
    entry1 = CoverageEntry(1, 1)
    entry2 = CoverageEntry(1, 2)
    annotation5: LineAnnotation = LineAnnotation(5, entry1, entry1, entry1, entry1)
    annotation: LineAnnotation = LineAnnotation(1, entry1, entry1, entry1, entry1)
    annotation2: LineAnnotation = LineAnnotation(2, entry1, entry2, entry1, entry1)
    annotation3: LineAnnotation = LineAnnotation(3, entry1, entry1, entry1, entry1)
    annotation4: LineAnnotation = LineAnnotation(4, entry1, entry1, entry1, entry1)
    annotations = [annotation, annotation2, annotation3, annotation4, annotation5]

    monkeypatch.setattr(
        "pynguin.testcase.llmlocalsearch.LLMLocalSearch.get_shortened_source_code",
        lambda *args, **kwargs: (source_lines, annotations),  # noqa: ARG005
    )
    mock_llm_agent.llm_test_case_handler.get_test_case_chromosomes_from_llm_results.return_value = (
        chromosomes
    )

    llm_local_search = LLMLocalSearch(tc_mock, objective, MagicMock(), MagicMock(), MagicMock())
    assert llm_local_search.llm_local_search(1) == result


def test_complex_objects(tc_mock, timer):
    objective = MagicMock()
    objective.has_improved.return_value = False
    int_statement = IntPrimitiveStatement(tc_mock, 42)
    int_statement_2 = IntPrimitiveStatement(tc_mock, 24)
    statement = FunctionStatement(tc_mock, MagicMock(), {"value": int_statement.ret_val})
    tc_mock.test_case.statements[0] = int_statement
    tc_mock.test_case.statements[1] = int_statement_2
    tc_mock.test_case.statements[2] = statement
    test_case_clone = MagicMock()
    test_case_clone.statements = [
        int_statement.clone(tc_mock, Mirror()),
        int_statement_2.clone(tc_mock, Mirror()),
        statement.clone(tc_mock, Mirror()),
    ]
    test_case_clone.clone.return_value = test_case_clone
    tc_mock.test_case.clone.side_effect = [tc_mock.test_case] * 10 + [test_case_clone]
    factory_mock = MagicMock()
    factory_mock.insert_random_call_on_object_at.return_value = False
    factory_mock.change_random_call.return_value = False

    local_search = ParametrizedStatementLocalSearch(tc_mock, 2, objective, factory_mock, timer)
    local_search.search()
    result: ParametrizedStatement = tc_mock.test_case.statements[2]
    assert int_statement.ret_val in result.get_variable_references()
