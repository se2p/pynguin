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
from typing import Type, Optional, Callable, Any, Tuple, cast, Union

_PRIMITIVES = {int, str, bool, float, complex}


def is_primitive_type(type_: Optional[Type]) -> bool:
    """Check if the given type is a primitive."""
    return type_ in _PRIMITIVES


def is_union_type(type_: Optional[Type]) -> bool:
    """Checks whether or not a given type is a Union."""
    if type_ is not None and hasattr(type_, "__origin__") and type_.__origin__ is Union:
        return True
    return False


def get_union_elements(type_: Optional[Type]) -> Optional[Tuple[Type]]:
    """Provides the elements of an Union type, if any is given.

    If the given parameter is not an Union type, the method returns `None`, otherwise it
    returns the elements of the Union as a Tuple.

    :param type_: The type to retrieve elements from
    :return: None if `type_` is not a Union, a tuple of elements otherwise
    """
    if not is_union_type(type_):
        return None
    assert type_ is not None, "This is already given by the is_union_type function"
    cast(Union, type_)
    return type_.__args__


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
