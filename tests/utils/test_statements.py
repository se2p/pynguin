# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
import collections
from unittest.mock import MagicMock

import pytest
from typing import Iterator

from pynguin.utils.statements import Statement, Sequence


@pytest.fixture
def sequence():
    return Sequence()


def test_statement():
    statement = Statement()
    assert isinstance(statement, Statement)


def test_sequence_append(sequence):
    statement = MagicMock(Statement)
    assert len(sequence) == 0
    sequence.append(statement)
    assert len(sequence) == 1


def test_sequence_append_wrong_type(sequence):
    statement = collections.OrderedDict()
    with pytest.raises(AssertionError):
        sequence.append(statement)
    assert len(sequence) == 0


def test_sequence_pop(sequence):
    statement_1 = MagicMock(Statement)
    statement_2 = MagicMock(Statement)
    sequence.append(statement_1)
    sequence.append(statement_2)
    assert sequence.pop() is statement_2
    assert len(sequence) == 1


def test_sequence_getitem(sequence):
    statement_1 = MagicMock(Statement)
    statement_2 = MagicMock(Statement)
    sequence.append(statement_1)
    sequence.append(statement_2)
    assert sequence[1] is statement_2


def test_sequence_add(sequence):
    sequence.append(MagicMock(Statement))
    sequence_2 = Sequence()
    sequence_2.append(MagicMock(Statement))
    result = sequence.__add__(sequence_2)
    assert len(result) == 2


def test_sequence_iter(sequence):
    statement_1 = MagicMock(Statement)
    statement_2 = MagicMock(Statement)
    sequence.append(statement_1)
    sequence.append(statement_2)
    assert isinstance(iter(sequence), Iterator)


def test_sequence_reversed(sequence):
    statement_1 = MagicMock(Statement)
    statement_2 = MagicMock(Statement)
    sequence.append(statement_1)
    sequence.append(statement_2)
    assert isinstance(reversed(sequence), Iterator)


def test_sequence_eq_wrong_type(sequence):
    assert sequence != collections.OrderedDict()


def test_sequence_eq_same(sequence):
    assert sequence == sequence


def test_sequence_eq_arcs(sequence):
    sequence.arcs = 42
    assert sequence == sequence
    assert sequence.arcs == 42


def test_sequence_output_values(sequence):
    sequence.output_values = {"foo": 42, "bar": 23}
    assert sequence.output_values == {"foo": 42, "bar": 23}


def test_sequence_counter(sequence):
    sequence.counter = 42
    assert sequence.counter == 42
