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
"""Provides various types of statements, similar to an AST."""
# pylint: disable=too-few-public-methods
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Union, Iterator, Optional, Type, TypeVar, Generic

# pylint: disable=invalid-name
T = TypeVar("T")


class StatementVisitor(Generic[T], metaclass=ABCMeta):
    """An abstract visitor for statements."""

    @abstractmethod
    def visit_expression(self, expression: "Expression") -> T:
        """Visits an expression.

        :param expression: The expression to visit
        :return: A generic return type T
        """

    @abstractmethod
    def visit_name(self, name: "Name") -> T:
        """Visits a name.

        :param name: The name to visit
        :return: A generic return type T
        """

    @abstractmethod
    def visit_attribute(self, attribute: "Attribute") -> T:
        """Visits an attribute.

        :param attribute: The attribute to visit
        :return: A generic return type T
        """

    @abstractmethod
    def visit_call(self, call: "Call") -> T:
        """Visits a call.

        :param call: The call to visit
        :return: A generic return type T
        """

    @abstractmethod
    def visit_assignment(self, assignment: "Assignment") -> T:
        """Visits an assignment.

        :param assignment: The assignment to visit
        :return: A generic return type T
        """


class Statement(Generic[T], metaclass=ABCMeta):
    """A simple program statement."""

    @abstractmethod
    def accept(self, visitor: StatementVisitor) -> T:
        """Accepts a statement visitor to visit the statement.

        :param visitor: The visitor
        """


class Expression(Statement):
    """An expression statement."""

    def accept(self, visitor: StatementVisitor) -> T:
        return visitor.visit_expression(self)


@dataclass(init=True)
class Name(Expression):
    """Represents a name as an expression."""

    identifier: str

    def accept(self, visitor: StatementVisitor) -> T:
        return visitor.visit_name(self)


@dataclass(init=True)
class Attribute(Expression):
    """Represents an attribute of a `Name` as an expression."""

    owner: Name
    attribute_name: str

    def accept(self, visitor: StatementVisitor) -> T:
        return visitor.visit_attribute(self)


@dataclass(init=True)
class Call(Expression):
    """Represents a function-call expression."""

    function: Expression
    arguments: List[Any]

    def accept(self, visitor: StatementVisitor) -> T:
        return visitor.visit_call(self)


@dataclass(init=True)
class Assignment(Expression):
    """Represents an assignment."""

    lhs: Expression
    rhs: Expression

    def accept(self, visitor: StatementVisitor) -> T:
        return visitor.visit_assignment(self)


@dataclass(init=True, repr=True, eq=True)
class FunctionSignature:
    """Represents a function signature."""

    module_name: Optional[str]
    class_name: Optional[str]
    method_name: str
    inputs: List[str]
    yield_type: Optional[Type] = None
    return_type: Optional[Type] = None
    instance_check_types: Dict[str, Type] = field(default_factory=dict)


class Sequence:
    """A sequence simply is a list of statements."""

    def __init__(self,) -> None:
        self._statements: List[Statement] = []
        self._arcs = None
        self._output_values: Dict[str, Any] = {}
        self._counter: int = 0

    def append(self, statement: Any) -> None:
        """Appends a statement object to the sequence.

        :param statement: The statement object to append
        """
        assert isinstance(statement, Statement)
        self._statements.append(statement)

    def pop(self) -> Statement:
        """Pops the last inserted statement from the sequence and returns it.

        :return: The last inserted statement from the sequence
        """
        return self._statements.pop()

    def __len__(self) -> int:
        return self._statements.__len__()

    def __getitem__(self, item: Union[int, slice]) -> Union[Statement, List[Statement]]:
        return self._statements.__getitem__(item)

    def __add__(self, other: Any) -> "Sequence":
        assert isinstance(other, Sequence)
        # pylint: disable=protected-access
        self._statements = self._statements.__add__(other._statements)
        return self

    def __iter__(self) -> Iterator[Statement]:
        return self._statements.__iter__()

    def __reversed__(self) -> Iterator[Statement]:
        return reversed(self._statements)

    # pylint: disable=protected-access
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Sequence):
            return False

        if not self._arcs or not other._arcs:
            return self._statements == other._statements

        return self._arcs == other._arcs

    @property
    def arcs(self):
        """Returns the arcs property."""
        return self._arcs

    @arcs.setter
    def arcs(self, arcs) -> None:
        self._arcs = arcs

    @property
    def output_values(self) -> Dict[str, Any]:
        """Returns the output values property."""
        return self._output_values

    @output_values.setter
    def output_values(self, output_values: Dict[str, Any]) -> None:
        self._output_values = output_values

    @property
    def counter(self) -> int:
        """Returns the counter property."""
        return self._counter

    @counter.setter
    def counter(self, counter: int) -> None:
        self._counter = counter
