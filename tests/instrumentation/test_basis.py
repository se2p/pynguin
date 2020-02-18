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
from types import ModuleType
from unittest.mock import MagicMock

from pynguin.instrumentation.basis import TRACER_NAME, get_tracer, set_tracer
from pynguin.instrumentation.tracking import ExecutionTracer


def test_get_tracer():
    module = MagicMock(ModuleType)
    tracer = MagicMock(ExecutionTracer)
    setattr(module, TRACER_NAME, tracer)
    assert get_tracer(module) == tracer


def test_set_tracer():
    module = MagicMock(ModuleType)
    tracer = MagicMock(ExecutionTracer)
    set_tracer(module, tracer)
    assert getattr(module, TRACER_NAME, tracer) == tracer
