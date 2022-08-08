#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides utilities to trace the usage of objects."""

from __future__ import annotations

import builtins
import contextlib
import dataclasses
import logging
import operator
from collections import defaultdict

from ordered_set import OrderedSet

LOGGER = logging.getLogger(__name__)


# Parts of the following code were taken from the awesome
# https://github.com/GrahamDumpleton/wrapt module and modified for our purposes.

# The wrapt library is under BSD 2-Clause "Simplified" License:
#
# Copyright (c) 2013-2022, Graham Dumpleton
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


@dataclasses.dataclass
class ProxyKnowledge:
    """The knowledge gathered by a proxy."""

    name: str

    # The depth of the proxy within the proxied object tree.
    # Zero indicates that it is the root.
    depth: int = 0

    # Symbols that have been accessed on this proxy.
    symbol_table: dict[str, ProxyKnowledge] = dataclasses.field(init=False)

    # The type against which this proxy was checked.
    # TODO(fk) do not record type checks originating from other proxies?
    # TODO(fk) do not record anything if it involves another proxy
    type_checks: OrderedSet[type] = dataclasses.field(default_factory=OrderedSet)

    # Maps argument positions to their types.
    arg_types: dict[int, OrderedSet[type]] = dataclasses.field(
        default_factory=lambda: defaultdict(OrderedSet)
    )

    def __post_init__(self):
        self.symbol_table = DepthDefaultDict(self.depth)

    def pretty(self) -> str:
        """Create a pretty representation of this object.

        Returns:
            A nicely formatted string
        """
        output = self.__get_indent(depth=self.depth) + f"'{self.name}'"
        if len(self.type_checks) > 0:
            output += f" (type-checks: {self.type_checks}"
        if len(self.arg_types) > 0:
            output += f" (arg-types: {self.arg_types.items()}"
        for children in self.symbol_table.values():
            output += "\n" + children.pretty()
        return output

    @staticmethod
    def __get_indent(depth: int) -> str:
        indent = "     " * (depth - 1)
        if depth > 0:
            indent += "^---"
        return indent

    @staticmethod
    def from_proxy(obj: ObjectProxy) -> ProxyKnowledge:
        """Extract knowledge from the given proxy.
        This is a convenience method, because the knowledge attribute is not visible
        on a proxy.

        Args:
            obj: the proxy from which we should extract knowledge

        Returns:
            The extracted knowledge.
        """
        return obj._self_proxy_knowledge

    def merge(self, other: ProxyKnowledge) -> None:
        """Merge the knowledge from the other proxy into this one.

        Args:
            other: The knowledge that should be merged into this one.
        """
        assert self.name == other.name
        assert self.depth == other.depth
        self.arg_types.update(other.arg_types)
        self.type_checks.update(other.type_checks)
        for symbol, knowledge in other.symbol_table.items():
            self.symbol_table[symbol].merge(knowledge)


class DepthDefaultDict(dict[str, ProxyKnowledge]):
    """Default dict which automatically creates a ProxyKnowledge for each requested
    and non-existing key."""

    def __init__(self, depth: int):
        super().__init__()
        self._depth = depth

    def __missing__(self, key):
        # Create knowledge for missing symbol
        res = self[key] = ProxyKnowledge(key, depth=self._depth + 1)
        return res


def proxify(log_arg_types=False, no_wrap_return=False):
    """Decorator to wrap the result of a dunder method in a proxy.

    Args:
        log_arg_types: Should we log the arguments?
        no_wrap_return: Some cases, e.g., __int__ don't allow a return value that is
            not an int, so in some cases we have to disable wrapping.

    Returns:
        A decorated function
    """

    def wrap(function):
        def wrapped(*args, **kwargs):
            self = args[0]
            knowledge = ProxyKnowledge.from_proxy(self)
            nested_knowledge = knowledge.symbol_table[function.__name__]
            if len(args) > 1:
                if any(isinstance(arg, ObjectProxy) for arg in args[1:]):
                    # Only record access but nothing more, if we interact with another
                    # proxy.
                    return function(*args, **kwargs)
                if log_arg_types:
                    for pos, arg in enumerate(args[1:]):
                        nested_knowledge.arg_types[pos].add(type(arg))
            if no_wrap_return:
                return function(*args, **kwargs)
            return ObjectProxy(function(*args, **kwargs), knowledge=nested_knowledge)

        return wrapped

    return wrap


class _ObjectProxyMethods:

    # We use properties to override the values of __module__ and
    # __doc__. If we add these in ObjectProxy, the derived class
    # __dict__ will still be setup to have string variants of these
    # attributes and the rules of descriptors means that they appear to
    # take precedence over the properties in the base class. To avoid
    # that, we copy the properties into the derived class type itself
    # via a meta class. In that way the properties will always take
    # precedence.

    @property  # type:ignore
    def __module__(self):
        return self.__wrapped__.__module__  # type:ignore # pylint:disable=no-member

    @__module__.setter
    def __module__(self, value):
        self.__wrapped__.__module__ = value  # type:ignore # pylint:disable=no-member

    @property  # type:ignore
    def __doc__(self):
        return self.__wrapped__.__doc__  # type:ignore # pylint:disable=no-member

    @__doc__.setter
    def __doc__(self, value):
        self.__wrapped__.__doc__ = value  # type:ignore # pylint:disable=no-member

    # We similar use a property for __dict__. We need __dict__ to be
    # explicit to ensure that vars() works as expected.

    @property
    def __dict__(self):
        return self.__wrapped__.__dict__  # type:ignore  # pylint:disable=no-member

    # Need to also propagate the special __weakref__ attribute for case
    # where decorating classes which will define this. If do not define
    # it and use a function like inspect.getmembers() on a decorator
    # class it will fail. This can't be in the derived classes.

    @property
    def __weakref__(self):
        return self.__wrapped__.__weakref__  # type:ignore  # pylint:disable=no-member


class _ObjectProxyMetaType(type):
    def __new__(cls, name, bases, dictionary):
        # Copy our special properties into the class so that they
        # always take precedence over attributes of the same name added
        # during construction of a derived class. This is to save
        # duplicating the implementation for them in all derived classes.

        dictionary.update(vars(_ObjectProxyMethods))

        return type.__new__(cls, name, bases, dictionary)


def unwrap(obj):
    """Unwrap the given object if it is a Proxy.

    Args:
        obj: The object to unwrap

    Returns:
        The unwrapped object
    """
    while isinstance(obj, ObjectProxy):
        obj = obj.__wrapped__  # type:ignore
    return obj


class ObjectProxy(metaclass=_ObjectProxyMetaType):
    """A proxy for (almost) any Python object."""

    def __init__(
        self, wrapped, knowledge: ProxyKnowledge | None = None, is_kwargs: bool = False
    ):
        object.__setattr__(self, "__wrapped__", wrapped)
        # What does this proxy know?
        object.__setattr__(
            self,
            "_self_proxy_knowledge",
            ProxyKnowledge(name="ROOT") if knowledge is None else knowledge,
        )
        # Is this proxy passed as **kwargs? If so, we can't return proxies from 'keys'
        # but must return the raw string objects.
        object.__setattr__(
            self,
            "_self_is_kwargs",
            is_kwargs,
        )

        # Python 3.2+ has the __qualname__ attribute, but it does not
        # allow it to be overridden using a property and it must instead
        # be an actual string object instead.

        try:
            object.__setattr__(self, "__qualname__", wrapped.__qualname__)
        except AttributeError:
            pass

        # Python 3.10 onwards also does not allow itself to be overridden
        # using a property and it must instead be set explicitly.

        try:
            object.__setattr__(self, "__annotations__", wrapped.__annotations__)
        except AttributeError:
            pass

    @property
    def __name__(self):
        return self.__wrapped__.__name__  # type:ignore

    @__name__.setter
    def __name__(self, value):
        self.__wrapped__.__name__ = value  # type:ignore

    @property
    def __class__(self):
        return self.__wrapped__.__class__  # type:ignore

    @__class__.setter
    def __class__(self, value):  # noqa: F811
        self.__wrapped__.__class__ = value  # type:ignore

    def __dir__(self):
        return dir(self.__wrapped__)  # type:ignore

    def __str__(self):
        return str(self.__wrapped__)  # type:ignore

    @proxify(no_wrap_return=True)
    def __bytes__(self):
        return bytes(self.__wrapped__)  # type:ignore

    # TODO(fk) remove this after debugging?
    def __repr__(self):
        return (
            f"<{type(self).__name__} at 0x{id(self):x} for "
            f"{type(self.__wrapped__).__name__} "  # type: ignore
            f"at 0x{id(self.__wrapped__):x}>"  # type: ignore
        )

    def __reversed__(self):
        return reversed(self.__wrapped__)  # type:ignore

    @proxify()
    def __round__(self, *args):
        return round(self.__wrapped__, *args)  # type:ignore

    def __mro_entries__(self, bases):  # pylint:disable=unused-argument
        return (self.__wrapped__,)  # type:ignore

    @proxify(log_arg_types=True, no_wrap_return=True)
    def __lt__(self, other):
        return self.__wrapped__ < other  # type:ignore

    @proxify(log_arg_types=True, no_wrap_return=True)
    def __le__(self, other):
        return self.__wrapped__ <= other  # type:ignore

    @proxify(log_arg_types=True, no_wrap_return=True)
    def __eq__(self, other):
        return self.__wrapped__ == other  # type:ignore

    @proxify(log_arg_types=True, no_wrap_return=True)
    def __ne__(self, other):
        return self.__wrapped__ != other  # type:ignore

    @proxify(log_arg_types=True, no_wrap_return=True)
    def __gt__(self, other):
        return self.__wrapped__ > other  # type:ignore

    @proxify(log_arg_types=True, no_wrap_return=True)
    def __ge__(self, other):
        return self.__wrapped__ >= other  # type:ignore

    def __hash__(self):
        return hash(self.__wrapped__)  # type:ignore

    @proxify(no_wrap_return=True)
    def __bool__(self):
        return bool(self.__wrapped__)  # type:ignore

    def __setattr__(self, name, value):
        if name.startswith("_self_"):
            object.__setattr__(self, name, value)

        elif name == "__wrapped__":
            object.__setattr__(self, name, value)
            try:
                object.__delattr__(self, "__qualname__")
            except AttributeError:
                pass
            try:
                object.__setattr__(self, "__qualname__", value.__qualname__)
            except AttributeError:
                pass
            try:
                object.__delattr__(self, "__annotations__")
            except AttributeError:
                pass
            try:
                object.__setattr__(self, "__annotations__", value.__annotations__)
            except AttributeError:
                pass

        elif name == "__qualname__":
            setattr(self.__wrapped__, name, value)  # type:ignore
            object.__setattr__(self, name, value)

        elif name == "__annotations__":
            setattr(self.__wrapped__, name, value)  # type:ignore
            object.__setattr__(self, name, value)

        elif hasattr(type(self), name):
            object.__setattr__(self, name, value)

        else:
            knowledge = ProxyKnowledge.from_proxy(self)
            accessed = knowledge.symbol_table[name]
            # Knowledge is created implicitly.
            assert accessed
            setattr(self.__wrapped__, name, value)  # type:ignore

    def __getattr__(self, name):
        # If we are being asked to lookup '__wrapped__' then the
        # '__init__()' method cannot have been called.
        if name == "__wrapped__":
            raise ValueError("wrapper has not been initialised")
        if name.startswith("_self_"):
            return object.__getattribute__(self, name)

        if name == "keys" and self._self_is_kwargs:
            # dict for **kwargs
            return getattr(self.__wrapped__, name)  # type:ignore

        # Append dummy in case of failed access
        knowledge = self._self_proxy_knowledge
        nested_knowledge = knowledge.symbol_table[name]
        proxy = ObjectProxy(
            getattr(self.__wrapped__, name),  # type:ignore
            knowledge=nested_knowledge,
        )
        return proxy

    def __delattr__(self, name):
        if name.startswith("_self_"):
            object.__delattr__(self, name)

        elif name == "__wrapped__":
            raise TypeError("__wrapped__ must be an object")

        elif name == "__qualname__":
            object.__delattr__(self, name)
            delattr(self.__wrapped__, name)  # type:ignore

        elif hasattr(type(self), name):
            object.__delattr__(self, name)

        else:
            delattr(self.__wrapped__, name)  # type:ignore

    @proxify(log_arg_types=True)
    def __add__(self, other):
        return self.__wrapped__ + other  # type:ignore

    @proxify(log_arg_types=True)
    def __sub__(self, other):
        return self.__wrapped__ - other  # type:ignore

    @proxify(log_arg_types=True)
    def __mul__(self, other):
        return self.__wrapped__ * other  # type:ignore

    @proxify(log_arg_types=True)
    def __truediv__(self, other):
        return operator.truediv(self.__wrapped__, other)  # type:ignore

    @proxify(log_arg_types=True)
    def __floordiv__(self, other):
        return self.__wrapped__ // other  # type:ignore

    @proxify(log_arg_types=True)
    def __mod__(self, other):
        return self.__wrapped__ % other  # type:ignore

    @proxify(log_arg_types=True)
    def __divmod__(self, other):
        return divmod(self.__wrapped__, other)  # type:ignore

    @proxify(log_arg_types=True)
    def __pow__(self, other, *args):
        return pow(self.__wrapped__, other, *args)  # type:ignore

    @proxify(log_arg_types=True)
    def __lshift__(self, other):
        return self.__wrapped__ << other  # type:ignore

    @proxify(log_arg_types=True)
    def __rshift__(self, other):
        return self.__wrapped__ >> other  # type:ignore

    @proxify(log_arg_types=True)
    def __and__(self, other):
        return self.__wrapped__ & other  # type:ignore

    @proxify(log_arg_types=True)
    def __xor__(self, other):
        return self.__wrapped__ ^ other  # type:ignore

    @proxify(log_arg_types=True)
    def __or__(self, other):
        return self.__wrapped__ | other  # type:ignore

    @proxify(log_arg_types=True)
    def __radd__(self, other):
        return other + self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rsub__(self, other):
        return other - self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rmul__(self, other):
        return other * self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rtruediv__(self, other):
        return operator.truediv(other, self.__wrapped__)  # type:ignore

    @proxify(log_arg_types=True)
    def __rfloordiv__(self, other):
        return other // self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rmod__(self, other):
        return other % self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rdivmod__(self, other):
        return divmod(other, self.__wrapped__)  # type:ignore

    @proxify(log_arg_types=True)
    def __rpow__(self, other, *args):
        return pow(other, self.__wrapped__, *args)  # type:ignore

    @proxify(log_arg_types=True)
    def __rlshift__(self, other):
        return other << self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rrshift__(self, other):
        return other >> self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rand__(self, other):
        return other & self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __rxor__(self, other):
        return other ^ self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __ror__(self, other):
        return other | self.__wrapped__  # type:ignore

    @proxify(log_arg_types=True)
    def __iadd__(self, other):  # type:ignore
        self.__wrapped__ += other  # type:ignore
        return self

    @proxify(log_arg_types=True)
    def __isub__(self, other):  # type:ignore
        self.__wrapped__ -= other  # type:ignore
        return self

    @proxify(log_arg_types=True)
    def __imul__(self, other):  # type:ignore
        self.__wrapped__ *= other  # type:ignore
        return self

    @proxify(log_arg_types=True)
    def __itruediv__(self, other):  # type:ignore
        # pylint:disable=attribute-defined-outside-init
        self.__wrapped__ = operator.itruediv(self.__wrapped__, other)  # type:ignore
        return self

    @proxify(log_arg_types=True)
    def __ifloordiv__(self, other):  # type:ignore
        self.__wrapped__ //= other
        return self

    @proxify(log_arg_types=True)
    def __imod__(self, other):  # type:ignore
        self.__wrapped__ %= other
        return self

    @proxify(log_arg_types=True)
    def __ipow__(self, other):  # type:ignore
        self.__wrapped__ **= other
        return self

    @proxify(log_arg_types=True)
    def __ilshift__(self, other):  # type:ignore
        self.__wrapped__ <<= other
        return self

    @proxify(log_arg_types=True)
    def __irshift__(self, other):  # type:ignore
        self.__wrapped__ >>= other
        return self

    @proxify(log_arg_types=True)
    def __iand__(self, other):  # type:ignore
        self.__wrapped__ &= other
        return self

    @proxify(log_arg_types=True)
    def __ixor__(self, other):  # type:ignore
        self.__wrapped__ ^= other
        return self

    @proxify(log_arg_types=True)
    def __ior__(self, other):  # type:ignore
        self.__wrapped__ |= other
        return self

    @proxify()
    def __neg__(self):
        return -self.__wrapped__

    @proxify()
    def __pos__(self):
        return +self.__wrapped__

    @proxify()
    def __abs__(self):
        return abs(self.__wrapped__)

    @proxify()
    def __invert__(self):
        return ~self.__wrapped__

    @proxify(no_wrap_return=True)
    def __int__(self):
        return int(self.__wrapped__)

    @proxify(no_wrap_return=True)
    def __float__(self):
        return float(self.__wrapped__)

    @proxify(no_wrap_return=True)
    def __complex__(self):
        return complex(self.__wrapped__)

    @proxify(no_wrap_return=True)
    def __index__(self):
        return operator.index(self.__wrapped__)

    @proxify()
    def __len__(self):
        # len turns result into an integer
        return len(self.__wrapped__)

    @proxify(log_arg_types=True)
    def __contains__(self, value):
        return value in self.__wrapped__

    @proxify(log_arg_types=True)
    def __getitem__(self, key):
        return self.__wrapped__[key]

    # TODO(fk) log value?
    @proxify(log_arg_types=True)
    def __setitem__(self, key, value):
        self.__wrapped__[key] = value

    @proxify()
    def __delitem__(self, key):
        del self.__wrapped__[key]

    def __enter__(self):
        return self.__wrapped__.__enter__()

    def __exit__(self, *args, **kwargs):
        return self.__wrapped__.__exit__(*args, **kwargs)

    def __iter__(self):
        knowledge = self._self_proxy_knowledge
        nested_knowledge = knowledge.symbol_table["__iter__"]
        for i in self.__wrapped__:
            proxy = ObjectProxy(i, knowledge=nested_knowledge)
            yield proxy

    # These do not give us any hint.
    # def __copy__(self):
    #     raise NotImplementedError('object proxy must define __copy__()')
    #
    # def __deepcopy__(self, memo):
    #     raise NotImplementedError('object proxy must define __deepcopy__()')
    #
    # def __reduce__(self):
    #     raise NotImplementedError(
    #             'object proxy must define __reduce_ex__()')
    #
    # def __reduce_ex__(self, protocol):
    #     raise NotImplementedError(
    #             'object proxy must define __reduce_ex__()')

    @proxify()
    def __call__(self, *args, **kwargs):
        return self.__wrapped__(*args, **kwargs)


@contextlib.contextmanager
def shim_isinstance():
    """Context manager that temporarily replaces isinstance with a shim.
    The shim is aware of ObjectProxies

    Yields:
        resets the shim
    """
    orig_isinstance = builtins.isinstance

    def shim(inst, types):
        # pylint:disable=unidiomatic-typecheck
        if type(inst) is ObjectProxy and types is not ObjectProxy:
            if orig_isinstance(types, tuple):
                ProxyKnowledge.from_proxy(inst).type_checks.update(types)
            else:
                ProxyKnowledge.from_proxy(inst).type_checks.add(types)
        return orig_isinstance(inst, types)

    builtins.isinstance = shim
    yield
    builtins.isinstance = orig_isinstance
