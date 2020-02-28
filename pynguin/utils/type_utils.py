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
"""Provides utilities when working with types."""
from inspect import isclass, isfunction
from typing import Type, Optional, Callable, Any

_PRIMITIVES = {int, str, bool, float, complex}


def is_primitive_type(type_: Optional[Type]) -> bool:
    """Check if the given type is a primitive."""
    return type_ in _PRIMITIVES


def class_in_module(module_name: str) -> Callable[[Any], bool]:
    """
    Returns a predicate which filters out any classes not directly defined in the given module.
    """
    return lambda member: isclass(member) and member.__module__ == module_name


def function_in_module(module_name: str) -> Callable[[Any], bool]:
    """
    Returns a predicate which filters out any functions not directly defined in the given module.
    """
    return lambda member: isfunction(member) and member.__module__ == module_name
