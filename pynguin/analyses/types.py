#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses for a module's type information."""
from __future__ import annotations

import abc
import dataclasses
import enum
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, get_type_hints

import networkx as nx
from networkx.drawing.nx_pydot import to_pydot
from ordered_set import OrderedSet

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


@dataclasses.dataclass(unsafe_hash=True, frozen=True)
class ClassWrapper:
    """A small wrapper around type, i.e., classes."""

    raw_type: type = dataclasses.field(hash=False, repr=False)
    name: str
    is_abstract: bool

    @staticmethod
    def from_type(raw_type: type) -> ClassWrapper:
        """Create type wrapper from given type.

        Naming in python is somehow misleading. 'type' actually only represents classes,
        but not any more complex types.

        Args:
            raw_type: the raw (class) type

        Returns:
            A wrapper for the given raw class.
        """
        name = f"{raw_type.__module__}.{raw_type.__qualname__}"
        is_abstract = inspect.isabstract(raw_type)
        return ClassWrapper(raw_type, name, is_abstract=is_abstract)


class InheritanceGraph:
    """Provides a simple inheritance graph relating various classes using their subclass
    relationships."""

    def __init__(self):
        self._graph = nx.DiGraph()

    def add_class(self, typ: ClassWrapper) -> None:
        """Add the given type to the graph.

        Args:
            typ: The type to add
        """
        self._graph.add_node(typ)

    def add_edge(self, *, super_class: ClassWrapper, sub_class: ClassWrapper) -> None:
        """Add an edge between two types.

        Args:
            super_class: superclass
            sub_class: subclass
        """
        self._graph.add_edge(super_class, sub_class)

    def get_subclasses(self, klass: ClassWrapper) -> OrderedSet[ClassWrapper]:
        """Provides all descendants of the given type. Includes klass.

        Args:
            klass: The class whose subtypes we want to query.

        Returns:
            All subclasses including klass
        """
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[ClassWrapper] = OrderedSet(
            nx.descendants(self._graph, klass)
        )
        result.add(klass)
        return result

    def get_superclasses(self, klass: ClassWrapper) -> OrderedSet[ClassWrapper]:
        """Provides all ancestors of the given class.

        Args:
            klass: The class whose supertypes we want to query.

        Returns:
            All superclasses including klass
        """
        if klass not in self._graph:
            return OrderedSet([klass])
        result: OrderedSet[ClassWrapper] = OrderedSet(nx.ancestors(self._graph, klass))
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
