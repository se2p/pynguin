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

from pynguin.generation.stoppingconditions.maxtimestoppingcondition import (
    MaxTimeStoppingCondition,
)


@pytest.fixture
def stopping_condition():
    return MaxTimeStoppingCondition()


def test_set_get_limit(stopping_condition):
    stopping_condition.set_limit(42)
    assert stopping_condition.limit() == 42


def test_is_not_fulfilled(stopping_condition):
    stopping_condition.reset()
    assert not stopping_condition.is_fulfilled()


def test_is_fulfilled(stopping_condition):
    stopping_condition.reset()
    stopping_condition.set_limit(0)
    assert stopping_condition.is_fulfilled()
