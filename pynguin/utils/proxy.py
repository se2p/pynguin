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
"""Provides a proxy that wraps objects to inspect them."""
import logging
import operator
from typing import Any, Iterator, TypeVar

Num = TypeVar("Num", int, float, complex)
T = TypeVar("T")  # pylint: disable=invalid-name

LOGGER = logging.getLogger(__name__)


def mark_error():
    """A decorator function to handle error tracking.

    It captures all raised exceptions during function execution, keeps track of them,
    and rethrows the exceptions.

    Returns:
        A decorating function

    Raises:  # noqa: DAR401
        TypeError: Raises the thrown exception to the outside since it is a user
            problem.  We only want to keep track of such occasions.
    """

    def decorate(function):
        def wrapper(*args):
            try:
                ret = function(*args)
                if ret == NotImplemented:
                    object.__setattr__(args[0], "_hasError", True)
                return ret
            except TypeError:
                object.__setattr__(args[0], "_hasError", True)
                raise
            except AttributeError:
                object.__setattr__(args[0], "_hasError", True)
                raise
            except ValueError as error:
                # TODO(sl) check this, in the handling of int() and float() because
                # the result seems to be very strange
                LOGGER.debug(
                    "Reached: TODO(sl) check this, in the handling of int() and float()"
                    " because the result seems to be very strange"
                )
                object.__setattr__(args[0], "_hasError", True)
                raise TypeError(error)

        return wrapper

    return decorate


class Proxy:
    """A transparent object proxy for (almost) all object.

    This code is taken from an ActiveState Code Recipe, which can be found at
    https://code.activestate.com/recipes/496741-object-proxying/.

    For further information on proxying types see, e.g.,
    - https://rszalski.github.io/magicmethods/#comparisons
    - https://theorangeduck.com/page/tracing-functions-python
    """

    __slots__ = ["_obj", "__weakref__"]

    def __init__(self, obj: Any) -> None:
        object.__setattr__(self, "_obj", obj)

    #
    # proxying (special cases)
    #
    def __getattribute__(self, item: str) -> Any:
        return getattr(object.__getattribute__(self, "_obj"), item)

    def __delattr__(self, item: str) -> None:
        delattr(object.__getattribute__(self, "_obj"), item)

    def __setattr__(self, key: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_obj"), key, value)

    def __nonzero__(self) -> bool:
        return bool(object.__getattribute__(self, "_obj"))

    def __str__(self) -> str:
        return str(object.__getattribute__(self, "_obj"))

    def __repr__(self) -> str:
        return repr(object.__getattribute__(self, "_obj"))

    def __hash__(self) -> int:
        return hash(object.__getattribute__(self, "_obj"))

    #
    # factories
    #
    _special_names = [
        "__abs__",
        "__add__",
        "__and__",
        "__call__",
        "__cmp__",
        "__coerce__",
        "__contains__",
        "__delitem__",
        "__delslice__",
        "__div__",
        "__divmod__",
        "__eq__",
        "__float__",
        "__floordiv__",
        "__ge__",
        "__getitem__",
        "__getslice__",
        "__gt__",
        "__hex__",
        "__iadd__",
        "__iand__",
        "__idiv__",
        "__idivmod__",
        "__ifloordiv__",
        "__ilshift__",
        "__imod__",
        "__imul__",
        "__int__",
        "__invert__",
        "__ior__",
        "__ipow__",
        "__irshift__",
        "__isub__",
        "__iter__",
        "__itruediv__",
        "__ixor__",
        "__le__",
        "__len__",
        "__lshift__",
        "__lt__",
        "__mod__",
        "__mul__",
        "__ne__",
        "__neg__",
        "__oct__",
        "__or__",
        "__pos__",
        "__pow__",
        "__radd__",
        "__rand__",
        "__rdiv__",
        "__rdivmod__",
        "__reduce__",
        "__reduce_ex__",
        "__repr__",
        "__reversed__",
        "__rfloordiv__",
        "__rlshift__",
        "__rmod__",
        "__rmul__",
        "__ror__",
        "__rpow__",
        "__rrshift__",
        "__rshift__",
        "__rsub__",
        "__rtruediv__",
        "__rxor__",
        "__setitem__",
        "__setslice__",
        "__sub__",
        "__truediv__",
        "__xor__",
        "next",
    ]

    @classmethod
    def _create_class_proxy(cls, the_class):
        def make_method(method_name):
            def method(self, *args, **kwargs):
                return getattr(object.__getattribute__(self, "_obj"), method_name)(
                    *args, **kwargs
                )

            return method

        namespace = {}
        for name in cls._special_names:
            if hasattr(the_class, name) and not hasattr(cls, name):
                namespace[name] = make_method(name)
        return type(f"{cls.__name__}({the_class.__name__})", (cls,), namespace)

    # pylint: disable=unused-argument
    def __new__(cls, obj, *args, **kwargs):
        try:
            cache = cls.__dict__["_class_proxy_cache"]
        except KeyError:
            cls._class_proxy_cache = cache = {}

        try:
            the_class = cache[obj.__class__]
        except KeyError:
            cache[obj.__class__] = the_class = cls._create_class_proxy(obj.__class__)
        ins = object.__new__(the_class)
        return ins


class MagicProxy(Proxy):
    """A proxy that captures all method calls to the wrapped object."""

    __slots__ = ["_obj", "_weakref", "_hasError", "_errorCode", "_instance_check_type"]

    def __init__(self, obj: Any) -> None:
        super().__init__(obj)
        object.__setattr__(self, "_hasError", False)
        object.__setattr__(self, "_errorCode", False)
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_instance_check_type", None)

    @mark_error()
    def __getattribute__(self, item: str) -> Any:
        if item in ["_hasError", "_errorCode", "_obj", "_instance_check_type"]:
            return object.__getattribute__(self, item)
        return getattr(object.__getattribute__(self, "_obj"), item)

    @mark_error()
    def __setattr__(self, key: str, value: Any) -> None:
        if key in ["_hasError", "_errorCode", "_obj", "_instance_check_type"]:
            object.__setattr__(self, key, value)
        else:
            setattr(object.__getattribute__(self, "_obj"), key, value)

    @mark_error()
    def __setitem__(self, key: str, value: Any) -> None:
        object.__getattribute__(self, "_obj")[key] = value

    @mark_error()
    def __getitem__(self, item: str) -> Any:
        return object.__getattribute__(self, "_obj")[item]

    @mark_error()
    def __delitem__(self, key: str) -> None:
        del object.__getattribute__(self, "_obj")[key]

    @mark_error()
    def __call__(self, *args, **kwargs):
        obj = object.__getattribute__(self, "_obj")
        if callable(obj):
            return obj(*args, **kwargs)
        # if the obj is not a callable we still want to trigger the exception
        return obj()

    @mark_error()
    def __len__(self) -> int:
        return len(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __truediv__(self, other: Num) -> float:
        return operator.truediv(object.__getattribute__(self, "_obj"), other)

    @mark_error()
    def __rtruediv__(self, other: Num) -> float:
        return other / object.__getattribute__(self, "_obj")

    @mark_error()
    def __floordiv__(self, other: Num) -> int:
        return object.__getattribute__(self, "_obj") // other

    @mark_error()
    def __rfloordiv__(self, other: Num) -> int:
        return other // object.__getattribute__(self, "_obj")

    @mark_error()
    def __abs__(self) -> Num:
        return abs(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __add__(self, other: Num) -> Num:
        return object.__getattribute__(self, "_obj") + other

    @mark_error()
    def __radd__(self, other: Num) -> Num:
        return other + object.__getattribute__(self, "_obj")

    @mark_error()
    def __sub__(self, other: Num) -> Num:
        return object.__getattribute__(self, "_obj") - other

    @mark_error()
    def __rsub__(self, other: Num) -> Num:
        return other - object.__getattribute__(self, "_obj")

    @mark_error()
    def __mod__(self, other: Num) -> Num:
        return object.__getattribute__(self, "_obj") % other

    @mark_error()
    def __rmod__(self, other: Num) -> Num:
        return other % object.__getattribute__(self, "_obj")

    @mark_error()
    # pylint: disable=unused-argument
    def __pow__(self, power: Num, modulo=None) -> Num:
        return object.__getattribute__(self, "_obj") ** power

    @mark_error()
    def __rpow__(self, other: Num) -> Num:
        return other ** object.__getattribute__(self, "_obj")

    @mark_error()
    def __mul__(self, other: Num) -> Num:
        return object.__getattribute__(self, "_obj") * other

    @mark_error()
    def __rmul__(self, other: Num) -> Num:
        return other * object.__getattribute__(self, "_obj")

    @mark_error()
    def __lt__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_obj") < other

    @mark_error()
    def __le__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_obj") <= other

    @mark_error()
    def __gt__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_obj") > other

    @mark_error()
    def __ge__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_obj") >= other

    @mark_error()
    def __eq__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_obj").__eq__(other)

    @mark_error()
    def __hash__(self) -> int:
        return hash(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __ne__(self, other: Any) -> bool:
        return object.__getattribute__(self, "_obj").__ne__(other)

    @mark_error()
    def __iter__(self) -> Iterator[T]:
        return iter(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __next__(self) -> T:
        return next(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __float__(self) -> float:
        return float(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __int__(self) -> float:
        return int(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __neg__(self) -> T:
        return operator.neg(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __pos__(self) -> int:
        return operator.pos(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __index__(self) -> int:
        return operator.index(object.__getattribute__(self, "_obj"))

    @mark_error()
    def __or__(self, other: bool) -> bool:
        return operator.or_(object.__getattribute__(self, "_obj"), other)

    @mark_error()
    def __ror__(self, other: bool) -> bool:
        return operator.or_(other, object.__getattribute__(self, "_obj"))

    @mark_error()
    def __lshift__(self, other: Num) -> Num:
        return operator.lshift(object.__getattribute__(self, "_obj"), other)

    @mark_error()
    def __rlshift__(self, other: Num) -> Num:
        return operator.lshift(other, object.__getattribute__(self, "_obj"))

    @mark_error()
    def __rshift__(self, other: Num) -> Num:
        return operator.rshift(object.__getattribute__(self, "_obj"), other)

    @mark_error()
    def __rrshift__(self, other: Num) -> Num:
        return operator.rshift(other, object.__getattribute__(self, "_obj"))

    @mark_error()
    def __matmul__(self, other: Any) -> Any:
        return operator.matmul(object.__getattribute__(self, "_obj"), other)

    @mark_error()
    def __rmatmul__(self, other: Any) -> Any:
        return operator.matmul(other, object.__getattribute__(self, "_obj"))

    @mark_error()
    def __and__(self, other: bool) -> bool:
        return operator.and_(object.__getattribute__(self, "_obj"), other)

    @mark_error()
    def __rand__(self, other: bool) -> bool:
        return operator.and_(other, object.__getattribute__(self, "_obj"))

    @mark_error()
    def __xor__(self, other: bool) -> bool:
        return operator.xor(object.__getattribute__(self, "_obj"), other)

    @mark_error()
    def __rxor__(self, other: bool) -> bool:
        return operator.xor(other, object.__getattribute__(self, "_obj"))
