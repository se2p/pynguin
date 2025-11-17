#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides utilities to trace the usage of objects."""

# Parts of the following code were taken from the awesome
# https://github.com/GrahamDumpleton/wrapt module and modified for our purposes.

# The wrapt library is under BSD 2-Clause "Simplified" License:
# Copyright (c) 2013-2022, Graham Dumpleton
# All rights reserved.
#  SPDX-FileCopyrightText: 2013-2022 Graham Dumpleton
#  SPDX-License-Identifier: BSD-2-Clause

from __future__ import annotations

import builtins
import contextlib
import dataclasses
import logging
import operator
from collections import defaultdict

from asciitree import BoxStyle, LeftAligned
from asciitree.drawing import BOX_LIGHT

from pynguin.utils.orderedset import OrderedSet, OrderedTypeSet

LOGGER = logging.getLogger(__name__)

# Max depth for proxies. Afterwards we don't wrap values anymore.
_MAX_PROXY_NESTING = 5

VALUE_TRACED_TYPES = {str}


@dataclasses.dataclass
class UsageTraceNode:
    """The knowledge gathered by a proxy."""

    name: str

    # The depth of the proxy within the proxied object tree.
    # Zero indicates that it is the root.
    depth: int = 0

    # Attributes that have been accessed on this proxy.
    children: dict[str, UsageTraceNode] = dataclasses.field(init=False)

    # The type against which this proxy was checked.
    type_checks: OrderedTypeSet = dataclasses.field(default_factory=OrderedTypeSet)

    # Maps argument positions to their types.
    arg_types: dict[int, OrderedSet[type]] = dataclasses.field(
        default_factory=lambda: defaultdict(OrderedSet)
    )

    # Maps argument positions to used values.
    arg_values: dict[int, OrderedSet[object]] = dataclasses.field(
        default_factory=lambda: defaultdict(OrderedSet)
    )

    def __post_init__(self):
        """Initialize the attribute with a specific dictionary."""
        self.children = DepthDefaultDict(self.depth)

    def find_path(self, path: tuple[str, ...]) -> UsageTraceNode | None:
        """Check if this usage trace tree has the given path.

        Args:
            path: The path to check

        Returns:
            The usage trace node at the end of the path, if it exists, otherwise None.
        """
        assert len(path) > 0, "Expected non-empty path."
        current = self
        for element in path:
            if element in current.children:
                current = current.children[element]
            else:
                return None
        return current

    def pretty(self) -> str:
        """Create a pretty representation of this object.

        Returns:
            A nicely formatted string
        """
        tree = LeftAligned(
            draw=BoxStyle(gfx=BOX_LIGHT, label_space=0, label_format="[{}]", indent=0)
        )
        return tree({self._format_str(): self._format_children()})

    def __len__(self) -> int:
        """Yield the length of a usage-trace node.

        The length is defined by the length of its children, argument types, and type
        checks.

        Returns:
            The length of a usage-trace node
        """
        return len(self.children) + len(self.arg_types) + len(self.type_checks)

    def _format_str(self):
        output = f"'{self.name}'"
        if len(self.type_checks) > 0:
            output += (
                ", type_checks: {" + ", ".join([check.__name__ for check in self.type_checks]) + "}"
            )
        if len(self.arg_types) > 0:
            output += (
                ", arg_types: {"
                + ", ".join([
                    str(idx) + ": {" + ", ".join([tp.__name__ for tp in types]) + "}"
                    for idx, types in self.arg_types.items()
                ])
                + "}"
            )
        if len(self.arg_values) > 0:
            output += (
                ", arg_values: {"
                + ", ".join([
                    str(idx) + ": {" + ", ".join([repr(val) for val in values]) + "}"
                    for idx, values in self.arg_values.items()
                ])
                + "}"
            )

        return output

    def _format_children(self):
        return {
            child._format_str(): child._format_children()  # noqa: SLF001
            for child in self.children.values()
        }

    @staticmethod
    def from_proxy(obj: ObjectProxy) -> UsageTraceNode:
        """Extract knowledge from the given proxy.

        This is a convenience method, because the knowledge attribute is not visible
        on a proxy.

        Args:
            obj: the proxy from which we should extract knowledge

        Returns:
            The extracted knowledge.
        """
        return obj._self_usage_trace_node  # noqa: SLF001

    def merge(self, other: UsageTraceNode) -> None:
        """Merge the knowledge from the other proxy into this one.

        Args:
            other: The knowledge that should be merged into this one.
        """
        assert self.name == other.name
        assert self.depth == other.depth
        self.arg_types.update(other.arg_types)
        self.type_checks.update(other.type_checks)
        self.arg_values.update(other.arg_values)
        for attr, knowledge in other.children.items():
            self.children[attr].merge(knowledge)


class DepthDefaultDict(dict[str, UsageTraceNode]):  # noqa: FURB189
    """A dictionary creating a UsageTraceNode automatically for each key.

    The implementation creates a UsageTraceNode for each requested and non-existing key.
    """

    def __init__(self, depth: int) -> None:
        """Initializes the dictionary.

        Args:
            depth: The depth of the trace
        """
        super().__init__()
        self._depth = depth

    def __missing__(self, key: str) -> UsageTraceNode:
        """Creates the knowledge for a missing key.

        Args:
            key: The name of the key

        Returns:
            The instance of this dictionary
        """
        res = self[key] = UsageTraceNode(key, depth=self._depth + 1)
        return res


def proxify(*, log_args=False, no_wrap_return=False):
    """Decorator method to trace the usage of a method on a proxy.

    1. Unwraps the proxy.
    2. Stores the access to the method
    3. Stores the argument types if requested.
    4. Stores the argument values if requested and if the type is in VALUE_TRACED_TYPES.
    5. Wraps the result in a proxy object (unless requested otherwise).

    Args:
        log_args: Should we store the arguments (types and values)?
        no_wrap_return: Some cases, e.g., __int__ don't allow a return value that is
            not an int, so in some cases we have to disable wrapping.

    Returns:
        A decorated function
    """

    def wrap(function):
        def wrapped(*args, **kwargs):
            self = args[0]
            knowledge = UsageTraceNode.from_proxy(self)
            nested_knowledge = knowledge.children[function.__name__]
            if len(args) > 1:
                if any(isinstance(arg, ObjectProxy) for arg in args[1:]):
                    # Only record access but nothing more, if we interact with another
                    # proxy.
                    return function(*args, **kwargs)
                if log_args:
                    # Store argument types
                    for pos, arg in enumerate(args[1:]):
                        nested_knowledge.arg_types[pos].add(type(arg))

                    # Store argument values
                    for pos, arg in enumerate(args[1:]):
                        if type(arg) in VALUE_TRACED_TYPES:
                            nested_knowledge.arg_values[pos].add(arg)
            if no_wrap_return or knowledge.depth >= _MAX_PROXY_NESTING:
                return function(*args, **kwargs)
            return ObjectProxy(function(*args, **kwargs), usage_trace=nested_knowledge)

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

    @property
    def __module__(self):
        return self.__wrapped__.__module__  # type: ignore[attr-defined]

    @__module__.setter
    def __module__(self, value):
        self.__wrapped__.__module__ = value  # type: ignore[attr-defined]

    @property
    def __doc__(self):
        return self.__wrapped__.__doc__  # type: ignore[attr-defined]

    @__doc__.setter
    def __doc__(self, value):
        self.__wrapped__.__doc__ = value  # type: ignore[attr-defined]

    # We similar use a property for __dict__. We need __dict__ to be
    # explicit to ensure that vars() works as expected.

    @property
    def __dict__(self):  # type: ignore[override]
        return self.__wrapped__.__dict__  # type: ignore[attr-defined]

    # Need to also propagate the special __weakref__ attribute for case
    # where decorating classes which will define this. If do not define
    # it and use a function like inspect.getmembers() on a decorator
    # class it will fail. This can't be in the derived classes.

    @property
    def __weakref__(self):
        return self.__wrapped__.__weakref__  # type: ignore[attr-defined]


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
        obj = obj.__wrapped__  # type:ignore[has-type]
    return obj


class ObjectProxy(metaclass=_ObjectProxyMetaType):  # noqa: PLR0904
    """A proxy for (almost) any Python object.

    Native types implemented in C might be problematic.
    """

    def __init__(
        self,
        wrapped,
        *,
        usage_trace: UsageTraceNode | None = None,
        is_kwargs: bool = False,
    ) -> None:
        """Initializes the proxy around a wrapped object.

        Args:
            wrapped: The wrapped object
            usage_trace: An optional usage-trace node
            is_kwargs: Whether the proxy is passed as **kwargs
        """
        object.__setattr__(self, "__wrapped__", wrapped)
        # What does this proxy know?
        object.__setattr__(
            self,
            "_self_usage_trace_node",
            UsageTraceNode(name="ROOT") if usage_trace is None else usage_trace,
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
        with contextlib.suppress(AttributeError):
            object.__setattr__(self, "__qualname__", wrapped.__qualname__)

        # Python 3.10 onwards also does not allow itself to be overridden
        # using a property and it must instead be set explicitly.
        with contextlib.suppress(AttributeError):
            object.__setattr__(self, "__annotations__", wrapped.__annotations__)

    @property
    def __name__(self):  # noqa: PLW3201
        return self.__wrapped__.__name__  # type:ignore[has-type]

    @__name__.setter
    def __name__(self, value):  # noqa: PLW3201
        self.__wrapped__.__name__ = value  # type:ignore[has-type]

    @property
    def __class__(self):
        return self.__wrapped__.__class__  # type:ignore[has-type]

    @__class__.setter
    def __class__(self, value):
        self.__wrapped__.__class__ = value  # type:ignore[has-type]

    def __dir__(self):
        return dir(self.__wrapped__)  # type:ignore[has-type]

    def __str__(self):
        return str(self.__wrapped__)  # type:ignore[has-type]

    @proxify(no_wrap_return=True)
    def __bytes__(self):
        return bytes(self.__wrapped__)  # type:ignore[has-type]

    def __repr__(self):
        return repr(self.__wrapped__)  # type:ignore[has-type]

    def __reversed__(self):
        return reversed(self.__wrapped__)  # type:ignore[has-type]

    @proxify()
    def __round__(self, *args):
        return round(self.__wrapped__, *args)  # type:ignore[has-type]

    def __mro_entries__(self, bases):
        return (self.__wrapped__,)  # type:ignore[has-type]

    @proxify(log_args=True, no_wrap_return=True)
    def __lt__(self, other):
        return self.__wrapped__ < other  # type:ignore[has-type]

    @proxify(log_args=True, no_wrap_return=True)
    def __le__(self, other):
        return self.__wrapped__ <= other  # type:ignore[has-type]

    @proxify(log_args=True, no_wrap_return=True)
    def __eq__(self, other):
        return self.__wrapped__ == other  # type:ignore[has-type]

    @proxify(log_args=True, no_wrap_return=True)
    def __ne__(self, other):
        return self.__wrapped__ != other  # type:ignore[has-type]

    @proxify(log_args=True, no_wrap_return=True)
    def __gt__(self, other):
        return self.__wrapped__ > other  # type:ignore[has-type]

    @proxify(log_args=True, no_wrap_return=True)
    def __ge__(self, other):
        return self.__wrapped__ >= other  # type:ignore[has-type]

    def __hash__(self):
        return hash(self.__wrapped__)  # type:ignore[has-type]

    @proxify(no_wrap_return=True)
    def __bool__(self):
        return bool(self.__wrapped__)  # type:ignore[has-type]

    def __setattr__(self, name, value):
        if name.startswith("_self_"):
            object.__setattr__(self, name, value)

        elif name == "__wrapped__":
            object.__setattr__(self, name, value)
            with contextlib.suppress(AttributeError):
                object.__delattr__(self, "__qualname__")
            with contextlib.suppress(AttributeError):
                object.__setattr__(self, "__qualname__", value.__qualname__)
            with contextlib.suppress(AttributeError):
                object.__delattr__(self, "__annotations__")
            with contextlib.suppress(AttributeError):
                object.__setattr__(self, "__annotations__", value.__annotations__)

        elif name in {"__qualname__", "__annotations__"}:
            setattr(self.__wrapped__, name, value)  # type:ignore[has-type]
            object.__setattr__(self, name, value)

        elif hasattr(type(self), name):
            object.__setattr__(self, name, value)

        else:
            node = UsageTraceNode.from_proxy(self)
            accessed = node.children[name]
            # Node is created implicitly.
            assert accessed is not None
            setattr(self.__wrapped__, name, value)  # type:ignore[has-type]

    def __getattr__(self, name):
        # If we are being asked to lookup '__wrapped__' then the
        # '__init__()' method cannot have been called.
        if name == "__wrapped__":
            raise ValueError("wrapper has not been initialised")
        if name.startswith("_self_"):
            return object.__getattribute__(self, name)

        if name == "keys" and self._self_is_kwargs:
            # dict for **kwargs
            return getattr(self.__wrapped__, name)  # type:ignore[has-type]

        node = self._self_usage_trace_node
        # Done before getattr, to make sure we store the access in case of an
        # exception
        child_node = node.children[name]
        if node.depth >= _MAX_PROXY_NESTING:
            return getattr(self.__wrapped__, name)  # type:ignore[has-type]
        return ObjectProxy(
            getattr(self.__wrapped__, name),  # type:ignore[has-type]
            usage_trace=child_node,
        )

    def __delattr__(self, name):
        if name.startswith("_self_"):
            object.__delattr__(self, name)

        elif name == "__wrapped__":
            raise TypeError("__wrapped__ must be an object")

        elif name == "__qualname__":
            object.__delattr__(self, name)
            delattr(self.__wrapped__, name)  # type:ignore[has-type]

        elif hasattr(type(self), name):
            object.__delattr__(self, name)

        else:
            delattr(self.__wrapped__, name)  # type:ignore[has-type]

    @proxify(log_args=True)
    def __add__(self, other):
        return self.__wrapped__ + other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __sub__(self, other):
        return self.__wrapped__ - other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __mul__(self, other):
        return self.__wrapped__ * other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __truediv__(self, other):
        return operator.truediv(self.__wrapped__, other)  # type:ignore[has-type]

    @proxify(log_args=True)
    def __floordiv__(self, other):
        return self.__wrapped__ // other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __mod__(self, other):
        return self.__wrapped__ % other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __divmod__(self, other):
        return divmod(self.__wrapped__, other)  # type:ignore[has-type]

    @proxify(log_args=True)
    def __pow__(self, other, *args):
        return pow(self.__wrapped__, other, *args)  # type:ignore[has-type]

    @proxify(log_args=True)
    def __lshift__(self, other):
        return self.__wrapped__ << other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rshift__(self, other):
        return self.__wrapped__ >> other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __and__(self, other):
        return self.__wrapped__ & other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __xor__(self, other):
        return self.__wrapped__ ^ other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __or__(self, other):
        return self.__wrapped__ | other  # type:ignore[has-type]

    @proxify(log_args=True)
    def __radd__(self, other):
        return other + self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rsub__(self, other):
        return other - self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rmul__(self, other):
        return other * self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rtruediv__(self, other):
        return operator.truediv(other, self.__wrapped__)  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rfloordiv__(self, other):
        return other // self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rmod__(self, other):
        return other % self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rdivmod__(self, other):
        return divmod(other, self.__wrapped__)  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rpow__(self, other, *args):
        return pow(other, self.__wrapped__, *args)  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rlshift__(self, other):
        return other << self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rrshift__(self, other):
        return other >> self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rand__(self, other):
        return other & self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __rxor__(self, other):
        return other ^ self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __ror__(self, other):
        return other | self.__wrapped__  # type:ignore[has-type]

    @proxify(log_args=True)
    def __iadd__(self, other):  # type:ignore[misc]
        self.__wrapped__ += other  # type:ignore[has-type]
        return self

    @proxify(log_args=True)
    def __isub__(self, other):  # type:ignore[misc]
        self.__wrapped__ -= other  # type:ignore[has-type]
        return self

    @proxify(log_args=True)
    def __imul__(self, other):  # type:ignore[misc]
        self.__wrapped__ *= other  # type:ignore[has-type]
        return self

    @proxify(log_args=True)
    def __itruediv__(self, other):  # type:ignore[misc]
        self.__wrapped__ = operator.itruediv(
            self.__wrapped__,  # type: ignore[has-type]
            other,
        )
        return self

    @proxify(log_args=True)
    def __ifloordiv__(self, other):  # type:ignore[misc]
        self.__wrapped__ //= other
        return self

    @proxify(log_args=True)
    def __imod__(self, other):  # type:ignore[misc]
        self.__wrapped__ %= other
        return self

    @proxify(log_args=True)
    def __ipow__(self, other):  # type:ignore[misc]
        self.__wrapped__ **= other
        return self

    @proxify(log_args=True)
    def __ilshift__(self, other):  # type:ignore[misc]
        self.__wrapped__ <<= other
        return self

    @proxify(log_args=True)
    def __irshift__(self, other):  # type:ignore[misc]
        self.__wrapped__ >>= other
        return self

    @proxify(log_args=True)
    def __iand__(self, other):  # type:ignore[misc]
        self.__wrapped__ &= other
        return self

    @proxify(log_args=True)
    def __ixor__(self, other):  # type:ignore[misc]
        self.__wrapped__ ^= other
        return self

    @proxify(log_args=True)
    def __ior__(self, other):  # type:ignore[misc]
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

    @proxify(log_args=True)
    def __contains__(self, value):
        return value in self.__wrapped__

    @proxify(log_args=True)
    def __getitem__(self, key):
        return self.__wrapped__[key]

    @proxify(log_args=True)
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
        node = self._self_usage_trace_node
        nested_node = node.children["__iter__"]
        if node.depth >= _MAX_PROXY_NESTING:
            yield from self.__wrapped__
        else:
            for i in self.__wrapped__:
                proxy = ObjectProxy(i, usage_trace=nested_node)
                yield proxy

    # These do not give us any hint.
    # def __copy__(self):
    #     raise NotImplementedError(
    #             'object proxy must define __copy__()')
    #
    # def __deepcopy__(self, memo):
    #     raise NotImplementedError(
    #             'object proxy must define __deepcopy__()')
    #
    # def __reduce__(self):
    #     raise NotImplementedError(
    #             'object proxy must define __reduce_ex__()')
    #
    # def __reduce_ex__(self, protocol):
    #     raise NotImplementedError(
    #             'object proxy must define __reduce_ex__()')

    @proxify(log_args=True)
    def __call__(self, *args, **kwargs):  # noqa: D102
        return self.__wrapped__(*args, **kwargs)


@contextlib.contextmanager
def shim_isinstance():
    """Context manager that temporarily replaces isinstance with a shim.

    The shim is aware of ObjectProxies.

    Yields:
        resets the shim
    """
    orig_isinstance = builtins.isinstance

    def shim(inst, types):
        if type(inst) is ObjectProxy:
            if types is ObjectProxy or orig_isinstance(types, ObjectProxy):
                return orig_isinstance(inst, types)
            if orig_isinstance(types, tuple):
                if any(typ is ObjectProxy or orig_isinstance(typ, ObjectProxy) for typ in types):
                    return orig_isinstance(inst, types)
                UsageTraceNode.from_proxy(inst).type_checks.update(types)
            else:
                UsageTraceNode.from_proxy(inst).type_checks.add(types)
        return orig_isinstance(inst, types)

    builtins.isinstance = shim
    yield
    builtins.isinstance = orig_isinstance
