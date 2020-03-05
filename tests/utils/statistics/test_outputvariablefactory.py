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
import pytest

import pynguin.configuration as config
from pynguin.utils.statistics.outputvariablefactory import (
    DirectSequenceOutputVariableFactory,
)
from pynguin.utils.statistics.statistics import RuntimeVariable


@pytest.fixture
def factory():
    return DirectSequenceOutputVariableFactory(
        RuntimeVariable.TotalExceptionsTimeline, 0
    )


def test_get_value(factory):
    factory.set_value(42)
    assert factory.get_value(None) == 42


def test_get_float():
    factory = DirectSequenceOutputVariableFactory.get_float(RuntimeVariable.Coverage)
    assert isinstance(factory.get_value(None), float)
    assert factory.get_value(None) == 0.0


def test_get_integer():
    factory = DirectSequenceOutputVariableFactory.get_integer(RuntimeVariable.Length)
    assert isinstance(factory.get_value(None), int)
    assert factory.get_value(None) == 0


def test_get_output_variables(factory):
    config.INSTANCE.budget = 0
    result = factory.get_output_variables()
    assert result == []
