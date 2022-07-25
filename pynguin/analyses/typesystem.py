#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses for a module's type information."""
from __future__ import annotations

import enum
import inspect
import logging
import types
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Sequence, TypeVar, get_type_hints

import networkx as nx
from networkx import has_path
from networkx.drawing.nx_pydot import to_pydot
from ordered_set import OrderedSet
from typing_inspect import is_union_type

from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.type_utils import filter_type_vars, wrap_var_param_type

_LOGGER = logging.getLogger(__name__)


@dataclass
class InferredSignature:
    """Encapsulates the types inferred for a method.

    The fields contain the following:

    * ``signature``: Holds an :py:class:`inspect.Signature` object as generated from
      the :py:func:`inspect.signature` function.
    * ``parameters``: A dictionary mapping a parameter name to its type, if any.
    * ``return_type``: The return type of a method, if any.

    The semantics of the ``parameters`` and ``return_type`` value for ``None`` is given
    as follows: the value ``None`` means that we do not yet know anything about this
    type; the value ``NoneType`` means that this parameter or return type is of type
    ``None``,  i.e., there is no parameter or return value.

    Consider the following example:

    * ``def foo()`` with ``return_type = None`` means we do not know what the return
      type is
    * ``def bar() -> None`` with ``return_type = type(None) = NoneType`` means that the
      function odes not return anything.

    The types shall not be updated directly!  One is supposed to use the methods
    :py:meth:`update_parameter_type` and :py:meth:`update_return_type` to update the
    parameter or return type, respectively.  These methods will also adjust the value of
    the ``signature`` field by generating a new :py:class:`inspect.Signature` instance
    accordingly.
    """

    signature: inspect.Signature
    parameters: dict[str, type | None] = field(default_factory=dict)
    return_type: type | None = Any  # type: ignore

    def update_parameter_type(
        self, parameter_name: str, parameter_type: type | None
    ) -> None:
        """Updates the type of one parameter.

        Args:
            parameter_name: The name of the parameter
            parameter_type: The new type of the parameter
        """
        assert parameter_name in self.parameters
        self.parameters[parameter_name] = parameter_type
        self.__update_signature_parameter(parameter_name, parameter_type)

    def update_return_type(self, return_type: type | None) -> None:
        """Update the return type.

        Args:
            return_type: The new return type
        """
        self.return_type = return_type
        self.__update_signature_return_type(return_type)

    def __update_signature_parameter(
        self, parameter_name: str, parameter_type: type | None
    ) -> None:
        current_parameter: inspect.Parameter | None = self.signature.parameters.get(
            parameter_name
        )
        assert current_parameter is not None, "Cannot happen due to previous check"
        new_parameter = current_parameter.replace(annotation=parameter_type)
        new_parameters = [
            new_parameter if key == parameter_name else value
            for key, value in self.signature.parameters.items()
        ]
        new_signature = self.signature.replace(parameters=new_parameters)
        self.signature = new_signature

    def __update_signature_return_type(self, return_type: type | None) -> None:
        new_signature = self.signature.replace(return_annotation=return_type)
        self.signature = new_signature


class TypeInferenceStrategy(enum.Enum):
    """The type-inference strategy."""

    NONE = enum.auto()
    TYPE_HINTS = enum.auto()


def infer_type_info(
    method: Callable,
    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS,
) -> InferredSignature:
    """Infers the type information for a callable.

    Args:
        method: The callable we try to infer type information for
        type_inference_strategy: Whether to incorporate type annotations

    Returns:
        The inference result

    Raises:
        ConfigurationException: in case an unknown type-inference strategy was selected
    """
    match type_inference_strategy:
        case TypeInferenceStrategy.TYPE_HINTS:
            return infer_type_info_with_types(method)
        case TypeInferenceStrategy.NONE:
            return infer_type_info_no_types(method)
        case _:
            raise ConfigurationException(
                f"Unknown type-inference strategy {type_inference_strategy}"
            )


def infer_type_info_no_types(method: Callable) -> InferredSignature:
    """Infers the method signature without incorporating type information.

    Args:
        method: The callable

    Returns:
        The inference result
    """
    if inspect.isclass(method) and hasattr(method, "__init__"):
        return infer_type_info_no_types(getattr(method, "__init__"))

    method_signature = inspect.signature(method)
    parameters: dict[str, type | None] = {}
    for param_name in method_signature.parameters:
        if param_name == "self":
            continue
        # var-positional and var-keyword need a dict or list/tuple,
        # which is technically not encoded in the type, but the kind of parameter,
        # so we also wrap this here.
        parameters[param_name] = wrap_var_param_type(
            Any, method_signature.parameters[param_name].kind  # type: ignore
        )
    return_type: type | None = Any  # type: ignore

    signature = InferredSignature(
        signature=method_signature, parameters=parameters, return_type=return_type
    )
    for param_name in method_signature.parameters:
        if param_name == "self":
            continue
        signature.update_parameter_type(param_name, Any)  # type:ignore
    signature.update_return_type(Any)  # type:ignore
    return signature


# The following classes are inspired by
# https://github.com/python/mypy/blob/master/mypy/types.py and most likely incomplete.
# The plan is to gradually expand this type representation.


T = TypeVar("T")


class ProperType(ABC):
    """Base class for all types. Might have to add another layer, like mypy's Type?."""

    @abstractmethod
    def accept(self, visitor: TypeVisitor) -> T:
        """Accept a type visitor

        Args:
            visitor: the visitor
        """

    def __repr__(self) -> str:
        return self.accept(TypeStringVisitor())


class AnyType(ProperType):
    """The Any Type"""

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_any_type(self)

    def __hash__(self):
        return hash(AnyType)

    def __eq__(self, other):
        return isinstance(other, AnyType)


class NoneType(ProperType):
    """The None type"""

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_none_type(self)

    def __hash__(self):
        return hash(NoneType)

    def __eq__(self, other):
        return isinstance(other, NoneType)


class Instance(ProperType):
    """An instance type of form C[T1, ..., Tn].
    C is a class.
    Args can be empty."""

    def __init__(self, typ: TypeInfo, args: Sequence[ProperType] = None):
        self.type = typ
        if args is None:
            args = []
        self.args = tuple(args)
        # Cached hash value
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_instance(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.type, self.args))
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, Instance):
            return False
        return self.type == other.type and self.args == other.args


class TupleType(ProperType):
    """Tuple type Tuple[T1, ..., Tn]. At least one argument."""

    def __init__(self, args: Sequence[ProperType], unknown_size: bool = False):
        self.args = tuple(args)
        assert len(self.args) > 0
        self.unknown_size = unknown_size
        # Cached hash value
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_tuple_type(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.args, self.unknown_size))
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, TupleType):
            return False
        return self.args == other.args and self.unknown_size == other.unknown_size


class UnionType(ProperType):
    """The union type Union[T1, ..., Tn] (at least one type argument)."""

    def __init__(self, items: Sequence[ProperType]):
        self.items = items
        assert len(self.items) > 0
        # Cached hash value
        self._hash: int | None = None

    def accept(self, visitor: TypeVisitor[T]) -> T:
        return visitor.visit_union_type(self)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(frozenset(self.items))
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, UnionType):
            return False
        return frozenset(self.items) == frozenset(other.items)


class TypeVisitor(Generic[T]):
    """A type visitor"""

    @abstractmethod
    def visit_any_type(self, left: AnyType) -> T:
        """Visit the Any type

        Args:
            left: the Any type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_none_type(self, left: NoneType) -> T:
        """Visit the None type

        Args:
            left: the None type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_instance(self, left: Instance) -> T:
        """Visit an instance

        Args:
            left: instance

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_tuple_type(self, left: TupleType) -> T:
        """Visit a tuple type

        Args:
            left: tuple

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_union_type(self, left: UnionType) -> T:
        """Visit a union

        Args:
            left: union

        Returns:
            result of the visit
        """


class TypeStringVisitor(TypeVisitor[str]):
    """A simple visitor to convert a proper type to a string."""

    def visit_any_type(self, left: AnyType) -> str:
        return "Any"

    def visit_none_type(self, left: NoneType) -> str:
        return "None"

    def visit_instance(self, left: Instance) -> str:
        rep = left.type.name
        if len(left.args) > 0:
            rep += "[" + self._sequence_str(left.args) + "]"
        return rep

    def visit_tuple_type(self, left: TupleType) -> str:
        return f"tuple[{self._sequence_str(left.args)}]"

    def visit_union_type(self, left: UnionType) -> str:
        return f"Union{self._sequence_str(left.items)}"

    def _sequence_str(self, typs: Sequence[ProperType]) -> str:
        return ", ".join(t.accept(self) for t in typs)


class _SubtypeVisitor(TypeVisitor[bool]):
    """A visitor to check the subtyping relationship between two types, i.e.,
    is left a subtype of right?

    There is no need to check 'right' for AnyType, as this is done outside.
    """

    def __init__(self, graph: InheritanceGraph, right: ProperType):
        """Create new visitor

        Args:
            graph: The inheritance graph.
            right: The right type.
        """
        self.graph = graph
        self.right = right

    def visit_any_type(self, left: AnyType) -> bool:  # pylint:disable=unused-argument
        # Any wins always
        return True

    def visit_none_type(self, left: NoneType) -> bool:  # pylint:disable=unused-argument
        # None cannot be subtyped
        # TODO(fk) handle protocols, e.g., hashable.
        return False

    def visit_instance(self, left: Instance) -> bool:
        if isinstance(self.right, Instance):
            # We only check for subclasses relation currently.
            # TODO(fk) handle generics :(
            return self.graph.is_subclass(left.type, self.right.type)
        return False

    def visit_tuple_type(self, left: TupleType) -> bool:
        if isinstance(self.right, TupleType):
            if len(left.args) != len(self.right.args):
                # TODO(fk) Handle unknown size.
                return False
            return all(
                self.graph.is_subtype(left_elem, right_elem)
                for left_elem, right_elem in zip(left.args, self.right.args)
            )
        return False

    def visit_union_type(self, left: UnionType) -> bool:
        if isinstance(self.right, UnionType):
            return all(
                self.graph.is_subtype(left_elem, self.right) for left_elem in left.items
            )
        return False


def infer_type_info_with_types(method: Callable) -> InferredSignature:
    """Infers the method signature while incorporating PEP484-style type information.

    Args:
        method: The callable

    Returns:
        The inference result
    """
    if inspect.isclass(method) and hasattr(method, "__init__"):
        return infer_type_info_with_types(getattr(method, "__init__"))

    method_signature = inspect.signature(method)
    parameters: dict[str, type | None] = {}
    try:
        hints = get_type_hints(method)
        # Sadly there is no guarantee that resolving the type hints actually works.
        # If the developers annotated something with an erroneous type hint we fall back
        # to no type hints, i.e., use Any.
    except NameError:
        hints = {}

    for param_name in method_signature.parameters:
        if param_name == "self":
            continue
        hint = hints.get(param_name, Any)
        hint = wrap_var_param_type(hint, method_signature.parameters[param_name].kind)
        hint = filter_type_vars(hint)
        parameters[param_name] = hint

    return_type: type | None = filter_type_vars(hints.get("return", Any))

    return InferredSignature(
        signature=method_signature, parameters=parameters, return_type=return_type
    )


class TypeInfo:
    """A small wrapper around type, i.e., classes.
    Corresponds 1:1 to a class."""

    def __init__(self, raw_type: type):
        """Create type info from the given type.

        Don't use this constructor directly (unless for testing purposes), instead ask
        the inheritance graph to give you a type info for the given raw type.

        Naming in python is somehow misleading, 'type' actually only represents classes,
        but not any more complex types.

        Args:
            raw_type: the raw (class) type
        """
        self.raw_type = raw_type
        self.name = raw_type.__name__
        self.qualname = raw_type.__qualname__
        self.full_name = TypeInfo.to_full_name(raw_type)
        self.is_abstract = inspect.isabstract(raw_type)
        # TODO(fk) store more information on attributes
        self.instance_attributes: OrderedSet[str] = OrderedSet()
        self.symbols: OrderedSet[str] = OrderedSet()

    @staticmethod
    def to_full_name(typ: type) -> str:
        """Get the full name of the given type

        Args:
            typ: The type for which we want a full name.

        Returns:
            The fully qualified name
        """
        return f"{typ.__module__}.{typ.__qualname__}"

    def __eq__(self, other) -> bool:
        if not isinstance(other, TypeInfo):
            return False
        return other.full_name == self.full_name

    def __hash__(self):
        return hash(self.full_name)

    def __str__(self):
        return (
            f"{self.full_name}"
            f"\nsymbols {self.symbols}"
            f"\ninstance-attributes {self.instance_attributes}"
        )


class InheritanceGraph:
    """Provides a simple inheritance graph relating various classes using their subclass
    relationships.

    Note that parents point to their children."""

    def __init__(self):
        self._graph = nx.DiGraph()
        self._types: dict[str, TypeInfo] = {}

    def add_edge(self, *, super_class: TypeInfo, sub_class: TypeInfo) -> None:
        """Add an edge between two types.

        Args:
            super_class: superclass
            sub_class: subclass
        """
        self._graph.add_edge(super_class, sub_class)

    def get_subclasses(self, klass: TypeInfo) -> OrderedSet[TypeInfo]:
        """Provides all descendants of the given type. Includes klass.

        Args:
            klass: The class whose subtypes we want to query.

        Returns:
            All subclasses including klass
        """
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[TypeInfo] = OrderedSet(nx.descendants(self._graph, klass))
        result.add(klass)
        return result

    def get_superclasses(self, klass: TypeInfo) -> OrderedSet[TypeInfo]:
        """Provides all ancestors of the given class.

        Args:
            klass: The class whose supertypes we want to query.

        Returns:
            All superclasses including klass
        """
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[TypeInfo] = OrderedSet(nx.ancestors(self._graph, klass))
        result.add(klass)
        return result

    def is_subclass(self, left: TypeInfo, right: TypeInfo) -> bool:
        """Is 'left' a subclass of 'right'?

        Args:
            left: left type info
            right: right type info

        Returns:
            True, if there is a subclassing path from left to right.
        """
        return has_path(self._graph, right, left)

    def is_subtype(self, left: ProperType, right: ProperType) -> bool:
        """Is 'left' a subtype of 'right'?

        This check is more than incomplete, but it takes into account
        that anything is a subtype of AnyType.

        See https://peps.python.org/pep-0483/ and https://peps.python.org/pep-0484/
        for more details

        Args:
            left: The left type
            right: The right type

        Returns:
            True, if left is a subtype of right.
        """
        if isinstance(right, AnyType):
            # trivial case
            return True
        if isinstance(right, UnionType) and not isinstance(left, UnionType):
            # Case that would be duplicated for each type, so we put it here.
            return any(self.is_subtype(left, right_elem) for right_elem in right.items)
        return left.accept(_SubtypeVisitor(self, right))

    @property
    def dot(self) -> str:
        """Create dot representation of this graph.

        Returns:
            A dot string.
        """
        dot = to_pydot(self._graph)
        return dot.to_string()

    def to_type_info(self, typ: type) -> TypeInfo:
        """Find type info for the given type.

        Args:
            typ: The raw type we want to convert.

        Returns:
            A type info object.
        """
        found = self._types.get(TypeInfo.to_full_name(typ))
        if found is not None:
            return found
        info = TypeInfo(typ)
        self._types[info.full_name] = info
        self._graph.add_node(info)
        return info

    def find_type_info(self, full_name: str) -> TypeInfo | None:
        """Find typeinfo for the given name.

        Args:
            full_name: The name to search for.

        Returns:
            Type info, if any.
        """
        return self._types[full_name]

    def convert_type_hint(
        self,
        hint: Any,
    ) -> ProperType:
        # pylint:disable=too-many-return-statements
        """Python's builtin functionality makes handling types during runtime really
        hard, because 1) this is not intended to be used at runtime and 2) there are a
        lot of different notations, due to the constantly evolving type hint system.
        We also cannot easily use mypy's type abstraction because it is 1) strongly
        encapsulated and not part of mypy's public API and 2) is designed to be used
        for static type checking. This method tries to translate type hints into our
        own type abstraction in order to make handling types less painful.

        This conversion is naive when compared to what sophisticated type checkers like
        mypy do, but it is hopefully sufficient for our purposes.
        This method only handles a very small subset of the types that we may
        encounter in the wild, but at least it allows use to better reason about types.
        This should be extended in the future to handle more cases.

        Args:
            hint: The type hint

        Returns:
            A proper type.
        """
        # We must handle a lot of special cases, so try to give an example for each one.

        if hint is typing.Any or hint is None:
            # typing.Any or empty
            return AnyType()
        if hint is type(None):  # noqa: E721
            # None
            return NoneType()
        if hint is tuple:
            # tuple
            # TODO(fk) Tuple without size. Should use tuple[Any, ...] ?
            #  But ... (ellipsis) is not a type.
            return TupleType([AnyType()], unknown_size=True)
        if typing.get_origin(hint) is tuple:
            # tuple[int, str] or typing.Tuple[int, str]
            return TupleType([self.convert_type_hint(t) for t in hint.__args__])
        if is_union_type(hint) or isinstance(hint, types.UnionType):
            # int | str or typing.Union[int, str]
            return UnionType([self.convert_type_hint(t) for t in hint.__args__])
        if isinstance(
            hint, (typing._BaseGenericAlias, types.GenericAlias)  # type:ignore
        ):
            # list[int, str] or List[int, str] or Dict[int, str] or set[str]
            return Instance(
                self.to_type_info(hint.__origin__),
                [self.convert_type_hint(t) for t in hint.__args__],
            )
        if isinstance(hint, type):
            # int or str or MyClass
            return Instance(self.to_type_info(hint), [])
        # TODO(fk) log unknown hints to so we can better understand what
        #  we should add next
        _LOGGER.debug("Unknown type hint: %s", hint)
        # Should raise an error in the future.
        return AnyType()
