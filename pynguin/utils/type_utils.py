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

from typing_inspect import is_union_type, get_args

PRIMITIVES = {int, str, bool, float, complex}


def is_primitive_type(type_: Optional[Type]) -> bool:
    """Check if the given type is a primitive."""
    return type_ in PRIMITIVES


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


def is_none_type(type_: Optional[Type]) -> bool:
    """Is the given type NoneType?"""
    return type_ is type(None)  # noqa: E721


def is_assignable_to(from_type: Optional[Type], to_type: Optional[Type]) -> bool:
    """A naive implementation to check if one type is assignable to another.
    Currently only unary types or union types are supported.

    :param from_type: The type annotation that is used as the source.
    :param to_type: The type which should be assigned to.
    :return: True if `from_` is assignable to `to`
    """
    if is_union_type(to_type):
        return from_type in get_args(to_type)
    return from_type == to_type
