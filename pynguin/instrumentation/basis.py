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
"""Defines the name of the tracer and utilities to get/set it."""
from types import ModuleType

from pynguin.instrumentation.tracking import ExecutionTracer

TRACER_NAME: str = "pynguin_tracer"


def get_tracer(module: ModuleType) -> ExecutionTracer:
    """Get the tracer which is attached to the given module."""
    return getattr(module, TRACER_NAME)


def set_tracer(module: ModuleType, tracer: ExecutionTracer) -> None:
    """Set the tracer of the given module.
    :param module: the module whose tracer shall be set.
    :param tracer: the tracer that should be set.
    """
    setattr(module, TRACER_NAME, tracer)
