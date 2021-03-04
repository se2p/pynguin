#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
"""Provides classes for the internal representation of types."""
from __future__ import annotations

import functools
import math
from abc import ABCMeta, abstractmethod
from typing import Any, Iterator, NamedTuple, Set, Type

from pynguin.analyses.module.inheritance import ClassInformation, InheritanceGraph


# pylint: disable=too-few-public-methods
class SignatureType(metaclass=ABCMeta):
    """An abstract base class for types in signatures."""


# pylint: disable=too-few-public-methods
class _UnknownType(SignatureType):
    """Represents an unknown type, i.e., a type without an annotation."""


# pylint: disable=too-few-public-methods
class _AnyType(SignatureType):
    """Represents any type, i.e., a type annotated with Any."""


class ConcreteType(SignatureType):
    """Represents a concrete type."""

    def __init__(self, class_information: ClassInformation) -> None:
        self._class_information = class_information

    @property
    def class_information(self) -> ClassInformation:
        """Provides the class information of this type.

        Returns:
            The class information
        """
        return self._class_information

    @property
    def type_name(self) -> str:
        """Provides the name of the class.

        Returns:
            The name of the class
        """
        return self._class_information.name

    @property
    def type_object(self) -> Type:
        """Provides the type of the class.

        Returns:
            The type of the class
        """
        return self._class_information.class_object


class SignatureElement(metaclass=ABCMeta):
    """An abstract base class for types in signatures."""

    @functools.total_ordering
    class _Element(NamedTuple):
        signature_type: SignatureType
        confidence: float

        def __eq__(self, other: Any) -> bool:
            if self is other:
                return True
            if not isinstance(other, SignatureElement._Element):
                return False
            return self.signature_type == other.signature_type and math.isclose(
                self.confidence, other.confidence, rel_tol=1e-6, abs_tol=1e-12
            )

        def __lt__(self, other: Any) -> bool:
            if not isinstance(other, SignatureElement._Element):
                raise TypeError(  # pylint: disable=raising-format-tuple
                    "'<' not supported between instances of "
                    "'SignatureElement._Element' and '%s'",
                    type(other),
                )
            return self.confidence < other.confidence

    def __init__(self) -> None:
        self._elements: Set[SignatureElement._Element] = {
            SignatureElement._Element(signature_type=unknown_type, confidence=0.0)
        }

    def add_element(self, signature: SignatureType, confidence: float) -> None:
        """Adds an element to the set of possible signature types.

        The confidence value must be from [0;1], otherwise a `ValueError` is raised.

        Args:
            signature: The element to add
            confidence: Its confidence

        Raises:
            ValueError: If the confidence level is not from [0;1]
        """

    def replace_element(self, signature: SignatureType, confidence: float) -> None:
        """Replace the elements confidence.

        If the element is not yet present it will be added.
        The confidence value must be from [0;1], otherwise a `ValueError` is raised.

        Args:
            signature: The element to consider
            confidence: The new confidence value

        Raises:
            ValueError: If the confidence level is not from [0;1]
        """

    def provide_random_type(self, respect_confidence: bool = True) -> SignatureType:
        """Provides a random type from the possible types.

        If the `respect_confidence` parameter is set, it will sample based on the
        confidence level, otherwise it will randomly choose from all types.

        Args:
            respect_confidence: Whether or not the confidence level shall be respected

        Returns:
            A random signature type
        """

    @property
    def elements(self) -> Set[SignatureElement._Element]:
        """Provides all types that are possible.

        Returns:
            All types that are possible
        """
        return self._elements

    @property
    def element_types(self) -> Iterator[SignatureType]:
        """Provides an iterator over the element types.

        Returns:
            An iterator over the element types
        """
        for sig_type, _ in self._elements:
            yield sig_type

    @abstractmethod
    def include_inheritance(self, inheritance_graph: InheritanceGraph) -> None:
        """Includes the information from an inheritance graph.

        Args:
            inheritance_graph: The inheritance graph to use
        """


class Parameter(SignatureElement):
    """Represents a parameter of a method."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name

    @property
    def name(self) -> str:
        """Provides the parameter name.

        Returns:
            The parameter name
        """
        return self._name

    def include_inheritance(self, inheritance_graph: InheritanceGraph) -> None:
        pass


class ReturnType(SignatureElement):
    """Represents the return type of a method."""

    def include_inheritance(self, inheritance_graph: InheritanceGraph) -> None:
        pass


unknown_type = _UnknownType()
any_type = _AnyType()
