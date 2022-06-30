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
import types
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Sequence, TypeVar, get_type_hints

import networkx as nx
from networkx.drawing.nx_pydot import to_pydot
from ordered_set import OrderedSet
from typing_inspect import is_union_type

from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.type_utils import filter_type_vars, wrap_var_param_type


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
    def visit_any_type(self, typ: AnyType) -> T:
        """Visit the Any type

        Args:
            typ: the Any type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_none_type(self, typ: NoneType) -> T:
        """Visit the None type

        Args:
            typ: the None type

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_instance(self, typ: Instance) -> T:
        """Visit an instance

        Args:
            typ: instance

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_tuple_type(self, typ: TupleType) -> T:
        """Visit a tuple type

        Args:
            typ: tuple

        Returns:
            result of the visit
        """

    @abstractmethod
    def visit_union_type(self, typ: UnionType) -> T:
        """Visit a union

        Args:
            typ: union

        Returns:
            result of the visit
        """


class TypeStringVisitor(TypeVisitor[str]):
    """A simple visitor to convert a proper type to a string."""

    def visit_any_type(self, typ: AnyType) -> str:
        return "Any"

    def visit_none_type(self, typ: NoneType) -> str:
        return "None"

    def visit_instance(self, typ: Instance) -> str:
        rep = typ.type.name
        if len(typ.args) > 0:
            rep += "[" + self._list_str(typ.args) + "]"
        return rep

    def visit_tuple_type(self, typ: TupleType) -> str:
        return f"tuple[{self._list_str(typ.args)}]"

    def visit_union_type(self, typ: UnionType) -> str:
        return f"Union{self._list_str(typ.items)}"

    def _list_str(self, typs: Sequence[ProperType]) -> str:
        res: list[str] = []
        for typ in typs:
            res.append(typ.accept(self))
        return ", ".join(res)


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

        Naming in python is somehow misleading. 'type' actually only represents classes,
        but not any more complex types.

        Args:
            raw_type: the raw (class) type
        """
        self.raw_type = raw_type
        self.name = raw_type.__name__
        self.qualname = raw_type.__qualname__
        self.full_name = f"{raw_type.__module__}.{raw_type.__qualname__}"
        self.is_abstract = inspect.isabstract(raw_type)
        # TODO(fk) store more information on attributes
        self.instance_attributes: OrderedSet[str] = OrderedSet()

    def __eq__(self, other) -> bool:
        if not isinstance(other, TypeInfo):
            return False
        return other.full_name == self.full_name

    def __hash__(self):
        return hash(self.full_name)

    def __str__(self):
        return self.full_name

    def add_instance_attrs(self, *attrs: str):
        """Add the given attribute names

        Args:
            *attrs: The names
        """
        self.instance_attributes.update(attrs)


class InheritanceGraph:
    """Provides a simple inheritance graph relating various classes using their subclass
    relationships."""

    def __init__(self):
        self._graph = nx.DiGraph()

    def add_class(self, typ: TypeInfo) -> None:
        """Add the given type to the graph.

        Args:
            typ: The type to add
        """
        self._graph.add_node(typ)

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

    @property
    def dot(self) -> str:
        """Create dot representation of this graph.

        Returns:
            A dot string.
        """
        dot = to_pydot(self._graph)
        return dot.to_string()


def convert_type_hint(
    hint: Any,
) -> ProperType:
    # pylint:disable=too-many-return-statements
    """Converts a type hint to a proper type.
    Probably will need a lot of special cases.

    Handles type hints from different versions, e.g.:
    - dict[K, V] == typing.Dict[K, V]
    - tuple[T1, T2, ...] == typing.Tuple[T1, T2, ...]
    - set[V] == typing.Set[V]
    - list[V] == typing.List[V]

    Args:
        hint: The type hint

    Returns:
        A proper type.
    """
    if hint is typing.Any or hint is None:
        return AnyType()
    if hint is type(None):  # noqa: E721
        return NoneType()
    if hint is tuple:
        # Tuple without size. Should use tuple[Any, ...] ?
        # But ... (ellipsis) is not a type.
        return TupleType([AnyType()], unknown_size=True)
    if typing.get_origin(hint) is tuple:
        return TupleType([convert_type_hint(t) for t in hint.__args__])
    if isinstance(hint, types.GenericAlias):
        return Instance(
            TypeInfo(hint.__origin__),
            [convert_type_hint(t) for t in hint.__args__],
        )
    if is_union_type(hint) or isinstance(hint, types.UnionType):
        return UnionType([convert_type_hint(t) for t in hint.__args__])
    if isinstance(hint, type):
        return Instance(TypeInfo(hint), [])
    # Fallback for now. Should raise an error in the future.
    return AnyType()
