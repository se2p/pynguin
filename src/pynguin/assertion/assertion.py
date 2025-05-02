#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a base class for assertions."""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any


if TYPE_CHECKING:
    import ast

    import pynguin.testcase.variablereference as vr

    from pynguin.slicer.executionflowbuilder import UniqueInstruction


class Assertion:
    """Base class for assertions."""

    def __init__(self):  # noqa: D107
        # this makes an assertion stateful, but is required for caching in slicing
        self._checked_instructions: list[UniqueInstruction] = []

    @property
    def checked_instructions(self) -> list[UniqueInstruction]:
        """The instructions that were checked by the execution of the assertion.

        Returns:
            The instructions that were checked by the execution of the assertion.
        """
        return self._checked_instructions

    @abstractmethod
    def accept(self, visitor: AssertionVisitor) -> None:
        """Accept an assertion visitor.

        Args:
            visitor: the visitor that is accepted.
        """

    @abstractmethod
    def clone(self, memo: dict[vr.VariableReference, vr.VariableReference]) -> Assertion:
        """Clone this assertion.

        Args:
            memo: Mapping from old to new variables.

        Returns: the cloned assertion
        """

    @abstractmethod
    def __eq__(self, other: object) -> bool:
        pass  # pragma: no cover

    @abstractmethod
    def __hash__(self) -> int:
        pass  # pragma: no cover


class ReferenceAssertion(Assertion, ABC):
    """An assertion on a single reference."""

    def __init__(self, source: vr.Reference):  # noqa: D107
        super().__init__()
        self._source = source

    @property
    def source(self) -> vr.Reference:
        """Provides the reference on which we assert something.

        Returns:
            The reference on which we assert something.
        """
        return self._source

    @source.setter
    def source(self, value: vr.Reference) -> None:
        """Set the reference to be used for assertions.

        Args:
            value (vr.Reference): The reference to set for assertions.
        """
        self._source = value


class TypeNameAssertion(ReferenceAssertion):
    """An assertion that a reference has a type with a certain name.

    We compare the string representation of the fully qualified name.
    Using an isinstance check would also be possible, but classes might not always
    be accessible, for example when nested inside a function.

    For example:
        int_0 = 42
        assert f"{type(int_0).__module__}.{type(int_0).__qualname__}" == "builtins.int"
    """

    def __init__(self, source: vr.Reference, module: str, qualname: str):  # noqa: D107
        super().__init__(source)
        self._module = module
        self._qualname = qualname

    @property
    def module(self) -> str:
        """Provides the module name.

        Returns:
            The module name
        """
        return self._module

    @property
    def qualname(self) -> str:
        """Provides the qualname name.

        Returns:
            The qualname
        """
        return self._qualname

    def accept(self, visitor: AssertionVisitor) -> None:  # noqa: D102
        visitor.visit_type_name_assertion(self)

    def clone(  # noqa: D102
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> TypeNameAssertion:
        return TypeNameAssertion(self._source.clone(memo), self._module, self._qualname)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, TypeNameAssertion)
            and self._source == other._source
            and self._module == other._module
            and self._qualname == other._qualname
        )

    def __hash__(self) -> int:
        return hash((self._source, self._module, self._qualname))

    def __repr__(self):
        return f"TypeNameAssertion({self._source!r}, {self._module}, {self._qualname})"


class FloatAssertion(ReferenceAssertion):
    """An assertion on the float value of a reference.

    For example:
        assert float_0 == pytest.approx(42, rel=0.01, abs=0.01)
    """

    def __init__(self, source: vr.Reference, value: float):  # noqa: D107
        super().__init__(source)
        self._value = value

    @property
    def value(self) -> float:
        """Provides the value.

        Returns:
            The float value
        """
        return self._value

    def accept(self, visitor: AssertionVisitor) -> None:  # noqa: D102
        visitor.visit_float_assertion(self)

    def clone(  # noqa: D102
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> FloatAssertion:
        return FloatAssertion(self.source.clone(memo), self._value)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, FloatAssertion)
            and self._source == other._source
            and self._value == other._value
        )

    def __hash__(self) -> int:
        return hash((self._source, self._value))

    def __repr__(self):
        return f"FloatAssertion({self._source!r}, {self._value!r})"


class ObjectAssertion(ReferenceAssertion):
    """An assertion on the object behind a reference.

    This can be anything where the object can be reliably copied, besides float, which
    is handled by FloatAssertion.

    For example:
        assert var_0 == [1,2,3]
        assert var_1 == {Foo.BAR}
        assert var_2 == "Foobar"
    """

    def __init__(self, source: vr.Reference, value: Any):  # noqa: D107
        super().__init__(source)
        self._object = value

    @property
    def object(self) -> Any:
        """Provides the object used for comparison.

        Returns:
            The object used for comparison.
        """
        return self._object

    def accept(self, visitor: AssertionVisitor) -> None:  # noqa: D102
        visitor.visit_object_assertion(self)

    def clone(  # noqa: D102
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> ObjectAssertion:
        return ObjectAssertion(self.source.clone(memo), self._object)

    def __eq__(self, other: Any) -> bool:  # noqa: PYI032
        return (
            isinstance(other, ObjectAssertion)
            and self._source == other._source
            and self._object == other._object
        )

    def __hash__(self) -> int:
        # We cannot include the value in the hash, as it might be unhashable.
        # For example, dicts, lists and sets are not hashable.
        return 17 * hash(self._source) + 31

    def __repr__(self):
        return f"ObjectAssertion({self._source!r}, {self._object!r})"


class IsInstanceAssertion(ReferenceAssertion):
    """An assertion that checks if a reference is an instance of a given type."""

    def __init__(  # noqa: D107
        self, source: vr.Reference, expected_type: ast.Attribute | ast.Name
    ):
        super().__init__(source)
        self._expected_type = expected_type

    @property
    def expected_type(self) -> ast.Attribute | ast.Name:
        """Provides the expected type.

        Returns:
            The expected type
        """
        return self._expected_type

    def accept(self, visitor: AssertionVisitor) -> None:  # noqa: D102
        visitor.visit_isinstance_assertion(self)

    def clone(  # noqa: D102
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> IsInstanceAssertion:
        return IsInstanceAssertion(self.source.clone(memo), self._expected_type)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, IsInstanceAssertion)
            and self._source == other._source
            and self._expected_type == other._expected_type
        )

    def __hash__(self) -> int:
        return hash((self._source, self._expected_type))

    def __repr__(self):
        return f"IsInstanceAssertion({self._source!r}, {self._expected_type!r})"


class CollectionLengthAssertion(ReferenceAssertion):
    """An assertion on the length of a reference.

    This can be necessary for a collection that contains elements that we can not
    directly assert on. Though this kind of assertion is less preferable because it is
    less precise.

    For example:
        assert len(var_0) == 42
    """

    def __init__(self, source: vr.Reference, length: int):  # noqa: D107
        super().__init__(source)
        self._length = length

    @property
    def length(self) -> int:
        """The expected length.

        Returns:
            The expected length.
        """
        return self._length

    def accept(self, visitor: AssertionVisitor) -> None:  # noqa: D102
        visitor.visit_collection_length_assertion(self)

    def clone(  # noqa: D102
        self, memo: dict[vr.VariableReference, vr.VariableReference]
    ) -> CollectionLengthAssertion:
        return CollectionLengthAssertion(self.source.clone(memo), self._length)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, CollectionLengthAssertion)
            and self._source == other._source
            and self._length == other._length
        )

    def __hash__(self) -> int:
        return hash((self._source, self._length))

    def __repr__(self):
        return f"CollectionLengthAssertion({self._source!r}, {self._length})"


class ExceptionAssertion(Assertion):
    """An assertion that indicates that a statement raised an exception."""

    def __init__(self, module: str, exception_type_name: str):
        """Create a new exception assertion.

        Args:
            module: The module of the raised exception.
            exception_type_name: The name of the raised exception.
        """
        super().__init__()
        self._module: str = module
        # We use the name here because the type may be defined multiple times,
        # for example during mutation analysis, however, equality on such types does not
        # hold
        self._exception_type_name: str = exception_type_name

    def accept(self, visitor: AssertionVisitor) -> None:  # noqa: D102
        visitor.visit_exception_assertion(self)

    def clone(  # noqa: D102
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

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ExceptionAssertion)
            and self._exception_type_name == other._exception_type_name
            and self._module == other._module
        )

    def __hash__(self) -> int:
        return hash((self._module, self._exception_type_name))

    def __repr__(self):
        return f"ExceptionAssertion({self._module}, {self._exception_type_name})"


class AssertionVisitor:
    """Abstract visitor for assertions."""

    @abstractmethod
    def visit_type_name_assertion(self, assertion: TypeNameAssertion) -> None:
        """Visit a type name assertion.

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
    def visit_isinstance_assertion(self, assertion: IsInstanceAssertion) -> None:
        """Visit an isInstance assertion.

        Args:
            assertion: the visited assertion

        """

    @abstractmethod
    def visit_collection_length_assertion(self, assertion: CollectionLengthAssertion) -> None:
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
