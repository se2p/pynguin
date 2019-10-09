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
from unittest.mock import MagicMock

from coverage import Coverage

from pynguin.generation.executor import Executor
from pynguin.utils.statements import Sequence


def test_accumulated_coverage():
    executor = Executor([])
    coverage = executor.accumulated_coverage
    assert isinstance(coverage, Coverage)


def test_load_modules():
    executor = Executor([])
    executor.load_modules()


def test_execute():
    executor = Executor([])
    executor.execute(MagicMock(Sequence))
