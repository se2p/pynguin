#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a base class for assertions."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pynguin.testcase.variablereference as vr


class Assertion:
    """Base class for assertions."""

    @abstractmethod
    def accept(self, visitor: AssertionVisitor) -> None:
        """Accept an assertion visitor.

        Args:
            visitor: the visitor that is accepted.
        """

    @abstractmethod
    def clone(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> Assertion:
        """Clone this assertion.

        Args:
            memo: Mapping from old to new variables.

        Returns: the cloned assertion
        """

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        pass  # pragma: no cover

    @abstractmethod
    def __hash__(self) -> int:
        pass  # pragma: no cover


class ReferenceAssertion(Assertion, ABC):
    """An assertion on a single reference."""

    def __init__(self, source: vr.Reference):
        self._source = source

    @property
    def source(self) -> vr.Reference:
        """Provides the reference on which we assert something.

        Returns:
            The reference on which we assert something.
        """
        return self._source


class NotNoneAssertion(ReferenceAssertion):
    """An assertion that a reference is not None.

    For example:
        assert var_0 is not None
    """

    def accept(self, visitor: AssertionVisitor) -> None:
        visitor.visit_not_none_assertion(self)

    def clone(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> NotNoneAssertion:
        return NotNoneAssertion(self._source.clone(memo))

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, NotNoneAssertion) and self._source == other._source

    def __hash__(self) -> int:
        return hash(self._source)


class FloatAssertion(ReferenceAssertion):
    """An assertion on the float value of a reference.

    For example:
        assert float_0 == pytest.approx(42, rel=0.01, abs=0.01)
    """

    def __init__(self, source: vr.Reference, value: float):
        super().__init__(source)
        self._value = value

    @property
    def value(self) -> float:
        """Provides the value.

        Returns:
            The float value
        """
        return self._value

    def accept(self, visitor: AssertionVisitor) -> None:
        visitor.visit_float_assertion(self)

    def clone(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> FloatAssertion:
        return FloatAssertion(self.source.clone(memo), self._value)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, FloatAssertion)
            and self._source == other._source
            and self._value == other._value
        )

    def __hash__(self) -> int:
        return hash((self._source, self._value))


class ObjectAssertion(ReferenceAssertion):
    """An assertion on the object behind a reference.

    This can be anything where the object can be reliably copied, besides float, which
    is handled by FloatAssertion.

    For example:
        assert var_0 == [1,2,3]
        assert var_1 == {Foo.BAR}
        assert var_2 == "Foobar"
    """

    def __init__(self, source: vr.Reference, value: Any):
        super().__init__(source)
        self._object = value

    @property
    def object(self) -> Any:
        """Provides the object used for comparison.

        Returns:
            The object used for comparison.
        """
        return self._object

    def accept(self, visitor: AssertionVisitor) -> None:
        visitor.visit_object_assertion(self)

    def clone(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> ObjectAssertion:
        return ObjectAssertion(self.source.clone(memo), self._object)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, ObjectAssertion)
            and self._source == other._source
            and self._object == other._object
        )

    def __hash__(self) -> int:
        # We cannot include the value in the hash, as it might be unhashable.
        # For example, dicts, lists and sets are not hashable.
        return 17 * hash(self._source) + 31


class CollectionLengthAssertion(ReferenceAssertion):
    """An assertion on the length of a reference.

    This can be necessary for a collection that contains elements that we can not
    directly assert on. Though this kind of assertion is less preferable because it is
    less precise.

    For example:
        assert len(var_0) == 42
    """

    def __init__(self, source: vr.Reference, length: int):
        super().__init__(source)
        self._length = length

    @property
    def length(self) -> int:
        """The expected length.

        Returns:
            The expected length.
        """
        return self._length

    def accept(self, visitor: AssertionVisitor) -> None:
        visitor.visit_collection_length_assertion(self)

    def clone(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> CollectionLengthAssertion:
        return CollectionLengthAssertion(self.source.clone(memo), self._length)

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, CollectionLengthAssertion)
            and self._source == other._source
            and self._length == other._length
        )

    def __hash__(self) -> int:
        return hash((self._source, self._length))


class ExceptionAssertion(Assertion):
    """An assertion that indicates that a statement raised an exception."""

    def __init__(self, module: str, exception_type_name: str):
        """Create a new exception assertion.

        Args:
            module: The module of the raised exception.
            exception_type_name: The name of the raised exception.
        """
        self._module: str = module
        # We use the name here because the type may be defined multiple times,
        # for example during mutation analysis, however, equality on such types does not
        # hold
        self._exception_type_name: str = exception_type_name

    def accept(self, visitor: AssertionVisitor) -> None:
        visitor.visit_exception_assertion(self)

    def clone(
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> Assertion:
        return ExceptionAssertion(self._module, self._exception_type_name)

    @property
    def exception_type_name(self) -> str:
        """Provides the name of the raised exception.

        Returns:
            the name of the raised exception.
        """
        return self._exception_type_name

    @property
    def module(self) -> str:
        """Provides the module of the raised exception.

        Returns:
            the module of the raised exception
        """
        return self._module

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, ExceptionAssertion)
            and self._exception_type_name == other._exception_type_name
            and self._module == other._module
        )

    def __hash__(self) -> int:
        return hash((self._module, self._exception_type_name))


class AssertionVisitor:
    """Abstract visitor for assertions."""

    @abstractmethod
    def visit_not_none_assertion(self, assertion: NotNoneAssertion) -> None:
        """Visit a none assertion.

        Args:
            assertion: the visited assertion

        """

    @abstractmethod
    def visit_float_assertion(self, assertion: FloatAssertion) -> None:
        """Visit a float assertion.

        Args:
            assertion: the visited assertion

        """

    @abstractmethod
    def visit_object_assertion(self, assertion: ObjectAssertion) -> None:
        """Visit an object assertion.

        Args:
            assertion: the visited assertion

        """

    @abstractmethod
    def visit_collection_length_assertion(
        self, assertion: CollectionLengthAssertion
    ) -> None:
        """Visit a collection length assertion.

        Args:
            assertion: the visited assertion

        """

    @abstractmethod
    def visit_exception_assertion(self, assertion: ExceptionAssertion) -> None:
        """Visit an exception assertion.

        Args:
            assertion: the visited assertion

        """
