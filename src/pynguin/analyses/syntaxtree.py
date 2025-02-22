#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides analyses implemented on the abstract syntax tree.

The implementation of this module contains some code adopted from the ``darglint``
library (https://github.com/terrencepreilly/darglint), which was released by Terrence
Reilly under MIT license.
"""

from __future__ import annotations

import ast
import dataclasses
import logging

from collections import deque
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeAlias

import astroid

from astroid.nodes.as_string import to_code


if TYPE_CHECKING:
    from collections.abc import Iterable


_LOGGER = logging.getLogger(__name__)
AstroidFunctionDef: TypeAlias = astroid.AsyncFunctionDef | astroid.FunctionDef
ASTFunctionDef: TypeAlias = ast.AsyncFunctionDef | ast.FunctionDef


def has_decorator(
    func: ASTFunctionDef,
    decorators: str | Iterable[str],
) -> bool:
    """Checks whether a function has one or more decorators.

    Args:
        func: The function node from the AST
        decorators: The name or a list of names of decorators to check

    Returns:
        Whether the function has the decorators
    """
    if isinstance(decorators, str):
        decorators = (decorators,)

    for decorator in func.decorator_list:
        if isinstance(decorator, ast.Name) and decorator.id in decorators:
            return True
    return False


class _FunctionScopedVisitorMixin(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.in_function: bool = False

    def visit_AsyncFunctionDef(  # noqa: N802
        self, node: ast.AsyncFunctionDef
    ) -> ast.AST:
        if not self.in_function:
            self.in_function = True
            return getattr(super(), "visit_AsyncFunctionDef", super().generic_visit)(node)
        return ast.Pass()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:  # noqa: N802
        if not self.in_function:
            self.in_function = True
            return getattr(super(), "visit_FunctionDef", super().generic_visit)(node)
        return ast.Pass()

    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:  # noqa: N802
        if not self.in_function:
            self.in_function = True
            return getattr(super(), "visit_Lambda", super().generic_visit)(node)
        return ast.Pass()


class _Context:
    """A context tracking exceptions and symbols."""

    def __init__(self) -> None:
        self.exceptions: set[str] = set()

        # If we are in a bare handler, we have to capture new exceptions raised
        # separately from the existing ones.  So, we copy the existing exceptions
        # over here.  This complicates the logic, for the calling class (as
        # contextual operations have to account for two cases), but it does not seem
        # avoidable.
        self.bare_handler_exceptions: set[str] | None = None

        # A lookup from variable names to AST nodes.  If the variable name occurs in
        # a raise exceptions, then the exception will be added using this lookup.
        self.variables: dict[str, str | list[str]] = {}

        # The error(s) which the current exception block is handling.
        self.handling: list[str] | None = None

    def set_in_bare_handler(self) -> None:
        """Move exceptions to bare handler."""
        self.bare_handler_exceptions = set(self.exceptions)
        self.remove_all_exceptions()

    def __get_attr_name(self, attr: ast.Attribute | ast.Name | ast.Tuple) -> list[str]:
        curr: Any = attr
        parts: list[str] = []

        # Assume finite depth of AST here
        while curr:
            if isinstance(curr, ast.Attribute):
                parts.append(curr.attr)
                curr = curr.value
            elif isinstance(curr, ast.Name):
                parts.append(curr.id)
                curr = None
            elif isinstance(curr, ast.Tuple):
                names: list[str] = []
                for node in curr.elts:
                    if isinstance(node, ast.Attribute | ast.Name):
                        names.extend(self.__get_attr_name(node))
                    else:
                        _LOGGER.error(
                            "While getting the names from a caught tuple of "
                            "exceptions, encountered something other than an "
                            "ast.Name: %s",
                            node.__class__.__name__,
                        )
                return names
            else:
                _LOGGER.error(
                    "While getting ast.Attribute representation a node had an unexpected type %s",
                    curr.__class__.__name__,
                )
                curr = None

        parts.reverse()
        return [".".join(parts)]

    @staticmethod
    def __get_name_name(name: ast.Name | ast.Tuple) -> str | list[str]:
        assert isinstance(name, ast.Name | ast.Tuple)
        if isinstance(name, ast.Name):
            return name.id
        return [node.id for node in name.elts if isinstance(node, ast.Name)]

    def __get_exception_name(self, raises: ast.Raise) -> str | list[str]:  # noqa: C901
        if isinstance(raises, str):
            return raises

        if isinstance(raises.exc, ast.Name):
            name = raises.exc.id
            if name in self.variables:
                return self.variables[name]
            return name
        if isinstance(raises.exc, ast.Call):
            if hasattr(raises.exc.func, "id"):
                return raises.exc.func.id
            if hasattr(raises.exc.func, "attr"):
                return raises.exc.func.attr
            _LOGGER.debug(
                "Raises function call has neither id nor attr, has only %s",
                str(dir(raises.exc.func)),
            )
        elif isinstance(raises.exc, ast.Attribute):
            return raises.exc.attr
        elif isinstance(raises.exc, ast.Subscript):
            id_repr = ""
            if hasattr(raises.exc.value, "id"):
                id_repr = raises.exc.value.id
            n_repr = ""
            if hasattr(raises.exc.slice, "value"):
                value = raises.exc.slice.value
                if hasattr(value, "n"):
                    n_repr = value.n
            return f"{id_repr}[{n_repr}]"
        elif raises.exc is None:
            if not self.handling:
                return ""
            if len(self.handling) == 1:
                return self.handling[0]
            return self.handling
        else:
            _LOGGER.debug("Unexpected type in raises expression: %s", raises.exc)
        return ""

    def add_exception(self, node: ast.Raise) -> set[str]:
        """Add an exception to the context.

        If the exception(s) do not have a name and do not have more children,
        then it is a bare raise.  In that case, we return the exception(s) to the
        parent context.

        Args:
            node: A raise AST node

        Returns:
            A list of exceptions to be passed up to the parent context
        """
        name = self.__get_exception_name(node)
        if not name:  # string `name` is empty
            if self.bare_handler_exceptions is not None:
                return self.bare_handler_exceptions | self.exceptions
            if self.exceptions:
                return self.exceptions
            if self.variables:
                values: set[str] = set()
                for value in self.variables.values():
                    if isinstance(value, list):
                        values |= set(value)
                    else:
                        values.add(value)
                return values
            _LOGGER.warning(
                "Unexpectedly had no exception name raised and no exception in context."
            )

        if isinstance(name, str):
            self.exceptions.add(name)
        elif isinstance(name, list):
            for part in name:
                self.exceptions.add(part)
        else:
            _LOGGER.warning("Node name extraction failed: %s", node)
        return set()

    def remove_exception(self, node: ast.Raise) -> None:
        """Remove an exception from the context.

        Args:
            node: The raise node
        """
        name = self.__get_exception_name(node)
        if isinstance(name, str) and name in self.exceptions:
            self.exceptions.remove(name)
            self.handling = [name]
        elif isinstance(name, list):
            self.handling = []
            for part in name:
                self.exceptions.remove(part)
                self.handling.append(part)

    def remove_all_exceptions(self) -> None:
        """Removes all exceptions."""
        self.exceptions.clear()

    def add_variable(self, variable: str, exception: ast.Name | ast.Tuple) -> None:
        """Add a variable to the context.

        Args:
            variable: The variable
            exception: The bound exception
        """
        self.variables[variable] = self.__get_name_name(exception)

    def set_handling(self, attr: ast.Attribute | ast.Name | ast.Tuple) -> None:
        """Set the handling.

        Args:
            attr: An attribute
        """
        self.handling = self.__get_attr_name(attr)

    def remove_variable(self, variable: str) -> None:
        """Remove a variable from this context.

        Args:
            variable: The variable
        """
        del self.variables[variable]

    def extend(self, other: _Context) -> None:
        """Merge this context with another context.

        Args:
            other: The other context
        """
        self.exceptions |= other.exceptions

    def finish_handling(self) -> None:
        """Finish the handling of exceptions in this context."""
        self.handling = None


class _RaiseVisitor(ast.NodeVisitor):
    """Inspects raised exceptions to figure out which get exposed outside the func."""

    def __init__(self) -> None:
        super().__init__()
        self.contexts = deque([_Context()])

    @property
    def exceptions(self) -> set[str]:
        """Provides the set of exceptions that are not handled.

        Returns:
            Provides the set of exceptions that are not handled
        """
        return self.contexts[0].exceptions

    @property
    def context(self) -> _Context:
        """Provides the outermost context.

        Returns:
            The outermost context
        """
        return self.contexts[-1]

    def visit_Raise(self, node: ast.Raise) -> ast.AST:  # noqa: N802
        bubbles = self.context.add_exception(node)
        if bubbles:
            assert len(self.contexts) >= 1
            if len(self.contexts) < 2:
                return self.generic_visit(node)
            parent_context = self.contexts[-2]
            parent_context.exceptions |= bubbles

        return self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802
        self.contexts.append(_Context())
        for child in node.body:
            self.visit(child)
        for handler in node.handlers:
            if handler.type:
                if handler.name and (isinstance(handler.type, ast.Name | ast.Tuple)):
                    self.context.add_variable(handler.name, handler.type)
                elif isinstance(handler.type, ast.Attribute | ast.Name | ast.Tuple):
                    self.context.set_handling(handler.type)
                else:
                    _LOGGER.error(
                        "While getting the types of exceptions in the handler, "
                        "expected to find an ast.Name, ast.Tuple, or ast.Attribute,"
                        "but got %s",
                        handler.type,
                    )
                identifier = getattr(handler.type, "id", None)
                if identifier:
                    self.context.remove_exception(identifier)

                self.generic_visit(handler)
                self.context.finish_handling()
            else:
                # Handle a bare exception.
                #
                # Since the bare exception handles all exceptions, we have to clear
                # all exceptions from the context.  However, exceptions could also be
                # raised from this handler.  So we cannot clear the exceptions first.
                # But if we clear the exceptions second, then remove any new
                # exceptions raised in the handler.  What we need, then, is to know
                # which new exceptions are raised, and clear all but them.  For that,
                # we use a temporary context.
                self.context.set_in_bare_handler()
                self.generic_visit(handler)

        for child in node.finalbody:
            self.visit(child)
        for child in node.orelse:
            self.visit(child)

        context = self.contexts.pop()
        self.context.extend(context)

    def visit_Assert(self, node: ast.Assert) -> ast.AST:  # noqa: N802
        # If we see an assert statement in the subject under test we expect that the
        # assertion can also be failing, thus it is legitimate to raise an
        # AssertionError.  Hence, we add the AssertionError to the set of raised
        # exceptions.
        self.visit_Raise(
            ast.Raise(
                exc=ast.Call(
                    func=ast.Name(id="AssertionError", ctx=ast.Load()),
                    args=[],
                    keywords=[],
                ),
            )
        )
        # Make sure that we also execute a visit_Assert method in another analysis
        # visitor class.
        return getattr(super(), "visit_Assert", super().generic_visit)(node)


class _YieldVisitor(ast.NodeVisitor):
    """A visitor checking for ``yield`` nodes."""

    def __init__(self) -> None:
        super().__init__()
        self.yields: list[ast.Yield | ast.YieldFrom] = []

    def visit_Yield(self, node: ast.Yield) -> ast.AST:  # noqa: N802
        self.yields.append(node)
        return self.generic_visit(node)

    def visit_YieldFrom(self, node: ast.YieldFrom) -> ast.AST:  # noqa: N802
        self.yields.append(node)
        return self.generic_visit(node)


class _ReturnVisitor(ast.NodeVisitor):
    """A visitor checking for ``return`` nodes."""

    def __init__(self) -> None:
        super().__init__()
        self.returns: list[ast.Return | None] = []

    def visit_Return(self, node: ast.Return) -> ast.AST:  # noqa: N802
        self.returns.append(node)
        return self.generic_visit(node)


class _AssertVisitor(ast.NodeVisitor):
    """A visitor checking for ``assert`` statements."""

    def __init__(self) -> None:
        super().__init__()
        self.asserts: list[ast.Assert] = []

    def visit_Assert(self, node: ast.Assert) -> ast.AST:  # noqa: N802
        self.asserts.append(node)
        # Make sure that we also execute a visit_Assert method in another analysis
        # visitor class.
        return getattr(super(), "visit_Assert", super().generic_visit)(node)


class FunctionAnalysisVisitor(
    _FunctionScopedVisitorMixin,  # needs to be first in order!
    _RaiseVisitor,
    _YieldVisitor,
    _ReturnVisitor,
    _AssertVisitor,
):
    """A visitor that analyses functions.

    It assumes that it will be only called on ``ast.FunctionDef`` or
    ``ast.AsyncFunctionDef`` nodes.
    """


@dataclasses.dataclass
class FunctionDescription:
    """Describes a function or method in the subject under test.

    Attributes:
        end_line_no: The last line number of the function (or -1)
        func: The AST node of the function
        has_empty_return: Whether the function has an empty ``return`` statement
        has_return: Whether the function has a ``return`` statement
        has_yield: Whether there is a ``yield`` statement in the function's body
        name: The name of the function
        raises: The (potentially empty) set of exceptions the function raises
        raises_assert: Whether the function raises any exceptions
        start_line_no: The first line number of the function
    """

    end_line_no: int
    func: AstroidFunctionDef
    has_empty_return: bool
    has_return: bool
    has_yield: bool
    name: str
    raises: set[str]
    raises_assert: bool
    start_line_no: int


def astroid_to_ast(astroid_in: AstroidFunctionDef) -> ASTFunctionDef:
    """Some part of the analysis only works with Pythons AST (for now).

    So it is necessary to convert astroid to AST.

    Args:
        astroid_in: The astroid function def

    Returns:
        The ast function def
    """
    # TODO(fk) port all of the analysis to astroid so this is no longer necessary.
    return ast.parse(to_code(astroid_in)).body[0]  # type: ignore[return-value]


def get_function_node_from_ast(
    tree: astroid.Module | astroid.ClassDef | None, name: str
) -> AstroidFunctionDef | None:
    """Get the AST Node that represents the function with the given name.

    Args:
        tree: The AST to search
        name: The name of the function.

    Returns:
        The (Async)FunctionDef Node, if any.
    """
    if tree is None:
        return None
    if name not in tree.locals:
        return None
    maybe_function = tree.locals[name][0]
    if isinstance(maybe_function, astroid.FunctionDef | astroid.AsyncFunctionDef):
        return maybe_function
    return None


def get_class_node_from_ast(tree: astroid.Module | None, name: str) -> astroid.ClassDef | None:
    """Get the AST Node that represents the class with the given name.

    Args:
        tree: The AST to search
        name: The name of the class.

    Returns:
        The ClassDef Node, if any.
    """
    if tree is None:
        return None
    if name not in tree.locals:
        return None
    maybe_class = tree.locals[name][0]
    if isinstance(maybe_class, astroid.ClassDef):
        return maybe_class
    return None


def get_function_description(
    func: AstroidFunctionDef | None,
) -> FunctionDescription | None:
    """Get a description of the given function, if any.

    Args:
        func: The function to describe.

    Returns:
        A description of the function.
    """
    if func is None:
        return None

    function_analysis = FunctionAnalysisVisitor()
    try:
        function_analysis.visit(astroid_to_ast(func))
    except SyntaxError:
        _LOGGER.debug("Analysis of %s failed", func.name)
        return None

    has_return = bool(function_analysis.returns)
    has_empty_return = False
    if has_return:
        return_value = function_analysis.returns[0]
        has_empty_return = return_value is not None and return_value.value is None

    return FunctionDescription(
        end_line_no=func.tolineno,
        func=func,
        has_empty_return=has_empty_return,
        has_return=has_return,
        has_yield=bool(function_analysis.yields),
        name=func.name,
        raises=function_analysis.exceptions,
        raises_assert=bool(function_analysis.asserts),
        start_line_no=func.fromlineno,
    )
