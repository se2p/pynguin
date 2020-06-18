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
import inspect
import numbers
import types
import typing
from inspect import isclass, isfunction
from typing import Any, Callable, Optional, Type

from typing_inspect import get_args, is_union_type

from pynguin.typeinference.strategy import InferredSignature

PRIMITIVES = {int, str, bool, float, complex}


def is_primitive_type(type_: Optional[Type]) -> bool:
    """Check if the given type is a primitive.

    Args:
        type_: a given type

    Returns:
        Whether or not the type is a primitive type
    """
    return type_ in PRIMITIVES


def class_in_module(module_name: str) -> Callable[[Any], bool]:
    """Returns a predicate which filters out any classes not directly defined in the
    given module.

    Args:
        module_name: the name of the model

    Returns:
        A filter predicate
    """
    return lambda member: isclass(member) and member.__module__ == module_name


def function_in_module(module_name: str) -> Callable[[Any], bool]:
    """Returns a predicate which filters out any functions not directly defined in the
    given module.

    Args:
        module_name: the name of the model

    Returns:
        A filter predicate
    """
    return lambda member: isfunction(member) and member.__module__ == module_name


def is_none_type(type_: Optional[Type]) -> bool:
    """Is the given type NoneType?

    Args:
        type_: a type to check

    Returns:
        Whether or not the given type is NoneType
    """
    return type_ is type(None)  # noqa: E721


def is_type_unknown(type_: Optional[Type]) -> bool:
    """Is the type of this variable unknown?

    Args:
        type_: a type to check

    Returns:
        Whether or not the given type is unknown
    """
    return type_ is None


def is_assignable_to(from_type: Optional[Type], to_type: Optional[Type]) -> bool:
    """A naive implementation to check if one type is assignable to another.

    Currently only unary types, Any and Union are supported.

    Args:
        from_type: The type annotation that is used as the source.
        to_type: The type which should be assigned to.

    Returns:
        True if `from_type` is assignable to `to_type`
    """
    if to_type == typing.Any:
        return True
    if is_union_type(to_type):
        return from_type in get_args(to_type)
    return from_type == to_type


def is_numeric(value: Any) -> bool:
    """Check if the given value is numeric.

    Args:
        value: an arbitrary value

    Returns:
        Whether or not the given value is numeric
    """
    return isinstance(value, numbers.Number)


def is_string(value: Any) -> bool:
    """Check if the given value is a string.

    Args:
        value: an arbitrary value

    Returns:
        Whether or not the given value is a string
    """
    return isinstance(value, str)


def get_class_that_defined_method(method: object) -> Optional[object]:
    """Retrieves the class that defines a method.

    Taken from https://stackoverflow.com/a/25959545/4293396

    Args:
        method: The method

    Returns:
        The class that defines the method
    """
    if inspect.ismethod(method):
        assert isinstance(method, types.MethodType)
        for cls in inspect.getmro(method.__self__.__class__):
            if cls.__dict__.get(method.__name__) is method:
                return cls
        method = method.__func__  # fallback to __qualname__ parsing
    if inspect.isfunction(method):
        assert isinstance(method, types.FunctionType)
        module = inspect.getmodule(method)
        attribute_name = method.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0]
        if not hasattr(module, attribute_name):
            return None
        cls = getattr(module, attribute_name)
        if isinstance(cls, type):
            return cls
    return getattr(method, "__objclass__", None)  # handle special descriptor objs


def should_skip_parameter(inf_sig: InferredSignature, parameter_name: str) -> bool:
    """There are some parameter types (*args, **kwargs) that are not handled as of now.

    This is a simple utility method to check if such a parameter should be skipped.

    Args:
        inf_sig: the inferred signature
        parameter_name: the name of the parameter

    Returns:
        Whether or not we should skip this parameter
    """
    parameter: inspect.Parameter = inf_sig.signature.parameters[parameter_name]
    return parameter.kind in (
        inspect.Parameter.VAR_POSITIONAL,
        inspect.Parameter.VAR_KEYWORD,
    )
