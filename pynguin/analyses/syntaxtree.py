#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses implemented on the abstract syntax tree.

The implementation of this module contains some code adopted from the ``darglint``
library (https://github.com/terrencepreilly/darglint), which was released by Terrence
Reilly under MIT license.
"""
from __future__ import annotations

import ast
import dataclasses
import enum
import logging
from collections import deque
from typing import Any, Iterable, Iterator

_LOGGER = logging.getLogger(__name__)


def has_decorator(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
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


def get_docstring(node: ast.AST) -> str | None:
    """Retrieves the docstring for an AST node if any.

    If the node does not provide a docstring, it raises a ``TypeError``.

    Args:
        node: The AST node

    Returns:
        The docstring for that node, if any
    """
    return ast.get_docstring(node)


def get_all_functions(
    tree: ast.AST,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yields all functions from an AST.

    Args:
        tree: The AST

    Yields:
        All functions from the AST
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def get_all_classes(tree: ast.AST) -> Iterator[ast.ClassDef]:
    """Yields all classes from an AST.

    Args:
        tree: The AST

    Yields:
        All classes from the AST
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            yield node


def get_all_methods(
    tree: ast.AST,
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yields all methods from an AST.

    Args:
        tree: The AST

    Yields:
        All methods from the AST
    """
    for class_ in get_all_classes(tree):
        yield from get_all_functions(class_)


def get_return_type(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Retrieves the return type of a function from the AST.

    Args:
        func: The function-definition node from the AST

    Returns:
        The function's return type, might be ``None``
    """
    if func.returns is not None and hasattr(func.returns, "id"):
        return getattr(func.returns, "id")
    return None


def get_line_number_for_function(func: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Retrieves the line number for a function from the AST.

    Args:
        func: The function-definition node from the AST

    Returns:
        The function's line number
    """
    line_number = func.lineno
    if hasattr(func, "args") and func.args.args:
        last_arg = func.args.args[-1]
        line_number = last_arg.lineno
    return line_number


class FunctionAndMethodVisitor(ast.NodeVisitor):
    """Extracts all functions, methods, and properties from an AST."""

    def __init__(self) -> None:
        self.__callables: set[ast.FunctionDef | ast.AsyncFunctionDef] = set()
        self.__methods: set[ast.FunctionDef | ast.AsyncFunctionDef] = set()
        self.__properties: set[ast.FunctionDef | ast.AsyncFunctionDef] = set()

    @property
    def functions(self) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Provides all traced functions.

        Returns:
            A list of all traced functions
        """
        return list(self.__callables - self.__methods - self.__properties)

    @property
    def methods(self) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Provides all traced methods.

        Returns:
            A list of all traced methods
        """
        return list(self.__methods)

    @property
    def properties(self) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        """Provides all traced properties.

        Returns:
            A list of all traced properties
        """
        return list(self.__properties)

    # pylint: disable=invalid-name, missing-docstring
    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        for item in node.body:
            if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)):
                if has_decorator(item, "property"):
                    self.__properties.add(item)
                else:
                    self.__methods.add(item)
        return self.generic_visit(node)

    # pylint: disable=invalid-name, missing-docstring
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.__callables.add(node)
        return self.generic_visit(node)

    # pylint: disable=invalid-name, missing-docstring
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.__callables.add(node)
        return self.generic_visit(node)


class _FunctionScopedVisitorMixin(ast.NodeVisitor):
    def __init__(self) -> None:
        super().__init__()
        self.in_function: bool = False

    # pylint: disable=invalid-name, missing-docstring
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        if not self.in_function:
            self.in_function = True
            return getattr(super(), "visit_AsyncFunctionDef", super().generic_visit)(
                node
            )
        return ast.Pass()

    # pylint: disable=invalid-name, missing-docstring
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if not self.in_function:
            self.in_function = True
            return getattr(super(), "visit_FunctionDef", super().generic_visit)(node)
        return ast.Pass()

    # pylint: disable=invalid-name, missing-docstring
    def visit_Lambda(self, node: ast.Lambda) -> ast.AST:
        if not self.in_function:
            self.in_function = True
            return getattr(super(), "visit_Lambda", super().generic_visit)(node)
        return ast.Pass()


class _AbstractStaticCallableVisitor(ast.NodeVisitor):
    """A visitor that checks for abstract or static methods."""

    def __init__(self) -> None:
        super().__init__()
        self.is_abstract: bool | None = None
        self.is_static: bool = False

    @staticmethod
    def __is_docstring(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )

    @staticmethod
    def __is_ellipsis(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and node.value.value is Ellipsis
        )

    # pylint: disable=invalid-name
    @staticmethod
    def __is_raise_NotImplementedException(node: ast.AST) -> bool:
        return isinstance(node, ast.Raise) and (
            (isinstance(node.exc, ast.Name) and node.exc.id == "NotImplementedError")
            or (
                isinstance(node.exc, ast.Call)
                and isinstance(node.exc.func, ast.Name)
                and node.exc.func.id == "NotImplementedError"
            )
        )

    # pylint: disable=invalid-name
    @staticmethod
    def __is_raise_NotImplemented(node: ast.AST) -> bool:
        return (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Name)
            and node.value.id == "NotImplemented"
        )

    def __analyse_pure_abstract(
        self, node: ast.AsyncFunctionDef | ast.FunctionDef
    ) -> bool:
        if not has_decorator(node, "abstractmethod"):
            return False

        children = len(node.body)
        if children > 2:
            return False
        if children == 2:
            if not self.__is_docstring(node.body[0]):
                return False

            statement = node.body[1]
        else:
            statement = node.body[0]

        return (
            isinstance(statement, ast.Pass)
            or self.__is_ellipsis(statement)
            or self.__is_raise_NotImplementedException(statement)
            or self.__is_raise_NotImplemented(statement)
            or (children == 1 and self.__is_docstring(statement))
        )

    @staticmethod
    def __analyse_static(node: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
        return has_decorator(node, "staticmethod")

    # pylint: disable=invalid-name, missing-docstring
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        self.is_abstract = self.__analyse_pure_abstract(node)
        self.is_static = self.__analyse_static(node)
        return self.generic_visit(node)

    # pylint: disable=invalid-name, missing-docstring
    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        self.is_abstract = self.__analyse_pure_abstract(node)
        self.is_static = self.__analyse_static(node)
        return self.generic_visit(node)


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
                    if isinstance(node, (ast.Attribute, ast.Name)):
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
                    "While getting ast.Attribute representation a node had an "
                    "unexpected type %s",
                    curr.__class__.__name__,
                )
                curr = None

        parts.reverse()
        return [".".join(parts)]

    @staticmethod
    def __get_name_name(name: ast.Name | ast.Tuple) -> str | list[str]:
        assert isinstance(name, (ast.Name, ast.Tuple))
        if isinstance(name, ast.Name):
            return name.id
        return [node.id for node in name.elts if isinstance(node, ast.Name)]

    # pylint: disable=too-many-branches, too-many-return-statements
    def __get_exception_name(self, raises: ast.Raise) -> str | list[str]:
        if isinstance(raises, str):
            return raises

        if isinstance(raises.exc, ast.Name):
            name = raises.exc.id
            if name in self.variables:
                return self.variables[name]
            return name
        if isinstance(raises.exc, ast.Call):
            if hasattr(raises.exc.func, "id"):
                return getattr(raises.exc.func, "id")
            if hasattr(raises.exc.func, "attr"):
                return getattr(raises.exc.func, "attr")
            _LOGGER.debug(
                "Raises function call has neither id nor attr, has only %s",
                str(dir(raises.exc.func)),
            )
        elif isinstance(raises.exc, ast.Attribute):
            return raises.exc.attr
        elif isinstance(raises.exc, ast.Subscript):
            id_repr = ""
            if hasattr(raises.exc.value, "id"):
                id_repr = getattr(raises.exc.value, "id")
            n_repr = ""
            if hasattr(raises.exc.slice, "value"):
                value = getattr(raises.exc.slice, "value")
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
        if name == "":
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
        """Add a variable to the context

        Args:
            variable: The variable
            exception: The bound exception
        """
        self.variables[variable] = self.__get_name_name(exception)

    def set_handling(self, attr: ast.Attribute | ast.Name | ast.Tuple) -> None:
        """Set the handling

        Args:
            attr: An attribute
        """
        self.handling = self.__get_attr_name(attr)

    def remove_variable(self, variable: str) -> None:
        """Remove a variable from this context

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

    # pylint: disable=invalid-name, missing-docstring
    def visit_Raise(self, node: ast.Raise) -> ast.AST:
        bubbles = self.context.add_exception(node)
        if bubbles:
            assert len(self.contexts) > 1
            if len(self.contexts) < 2:
                return self.generic_visit(node)
            parent_context = self.contexts[-2]
            parent_context.exceptions |= bubbles

        return self.generic_visit(node)

    # pylint: disable=invalid-name, missing-docstring
    def visit_Try(self, node: ast.Try) -> None:
        self.contexts.append(_Context())
        for child in node.body:
            self.visit(child)
        for handler in node.handlers:
            if handler.type:
                if handler.name and (isinstance(handler.type, (ast.Name, ast.Tuple))):
                    self.context.add_variable(handler.name, handler.type)
                elif isinstance(handler.type, (ast.Attribute, ast.Name, ast.Tuple)):
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

    # pylint: disable=invalid-name, missing-docstring
    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        # If we see an assert statement in the subject under test we expect that the
        # assertion can also be failing, thus it is legitimate to raise an
        # AssertionError.  Hence, we add the AssertionError to the set of raised
        # exceptions.
        self.visit_Raise(
            ast.Raise(
                exc=ast.Call(func=ast.Name(id="AssertionError", ctx=ast.Load())),
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

    # pylint: disable=invalid-name, missing-docstring
    def visit_Yield(self, node: ast.Yield) -> ast.AST:
        self.yields.append(node)
        return self.generic_visit(node)

    # pylint: disable=invalid-name, missing-docstring
    def visit_YieldFrom(self, node: ast.YieldFrom) -> ast.AST:
        self.yields.append(node)
        return self.generic_visit(node)


class _ArgumentVisitor(ast.NodeVisitor):
    """Reports the arguments a function contains."""

    def __init__(self) -> None:
        super().__init__()
        self.arguments: list[str] = []
        self.types: list[tuple[str, str | None]] = []

    def __add_arg_by_name(self, name: str, arg: ast.arg) -> None:
        self.arguments.append(name)
        if arg.annotation is not None and hasattr(arg.annotation, "id"):
            # TODO does this cover unions?
            self.types.append((name, getattr(arg.annotation, "id")))
        else:
            self.types.append((name, None))

    # pylint: disable=missing-docstring
    def visit_arguments(self, node: ast.arguments) -> ast.AST:
        for arg in node.posonlyargs:
            self.__add_arg_by_name(arg.arg, arg)

        for arg in node.args:
            self.__add_arg_by_name(arg.arg, arg)

        for arg in node.kwonlyargs:
            self.__add_arg_by_name(arg.arg, arg)

        if node.vararg is not None:
            name = f"*{node.vararg.arg}"
            self.__add_arg_by_name(name, node.vararg)

        if node.kwarg is not None:
            name = f"**{node.kwarg.arg}"
            self.__add_arg_by_name(name, node.kwarg)

        return self.generic_visit(node)


class _VariableVisitor(ast.NodeVisitor):
    """Collect variables."""

    def __init__(self) -> None:
        super().__init__()
        self.variables: list[ast.Name] = []

    # pylint: disable=invalid-name, missing-docstring
    def visit_Name(self, node: ast.Name) -> ast.AST:
        if hasattr(node, "ctx") and isinstance(node.ctx, ast.Store):
            self.variables.append(node)
        return self.generic_visit(node)


class _ReturnVisitor(ast.NodeVisitor):
    """A visitor checking for ``return`` nodes"""

    def __init__(self) -> None:
        super().__init__()
        self.returns: list[ast.Return | None] = []
        self.return_types: list[ast.AST | None] = []

    # pylint: disable=invalid-name, missing-docstring
    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.returns.append(node)
        return self.generic_visit(node)


class _AssertVisitor(ast.NodeVisitor):
    """A visitor checking for ``assert`` statements."""

    def __init__(self) -> None:
        super().__init__()
        self.asserts: list[ast.Assert] = []

    # pylint: disable=invalid-name, missing-docstring
    def visit_Assert(self, node: ast.Assert) -> ast.AST:
        self.asserts.append(node)
        # Make sure that we also execute a visit_Assert method in another analysis
        # visitor class.
        return getattr(super(), "visit_Assert", super().generic_visit)(node)


# pylint: disable=too-many-ancestors
class FunctionAnalysisVisitor(
    _FunctionScopedVisitorMixin,  # needs to be first in order!
    _AbstractStaticCallableVisitor,
    _RaiseVisitor,
    _YieldVisitor,
    _ArgumentVisitor,
    _VariableVisitor,
    _ReturnVisitor,
    _AssertVisitor,
):
    """A visitor that analyses functions.

    It assumes that it will be only called on ``ast.FunctionDef`` or
    ``ast.AsyncFunctionDef`` nodes.
    """


class FunctionType(enum.Enum):
    """Specifies the kind of function."""

    FUNCTION = enum.auto()
    """Denotes a function, i.e., a callable on the top level of the module."""

    METHOD = enum.auto()
    """Denotes a method, i.e., a callable that is part of a class."""

    PROPERTY = enum.auto()
    """Denotes a property, i.e., a callable that has the ``@property`` decorator."""


@dataclasses.dataclass
class FunctionDescription:  # pylint: disable=too-many-instance-attributes
    """Describes a function or method in the subject under test.

    Attributes:
        argument_names: The (potentially empty) list of arguments of the function
        argument_types: The list of arguments and their annotated type (or ``None``)
        docstring: The optional docstring of the function
        func: The AST node of the function
        has_empty_return: Whether the function has an empty ``return`` statement
        has_return: Whether the function has a ``return`` statement
        has_yield: Whether there is a ``yield`` statement in the function's body
        is_abstract: Whether the function is an abstract method of a class
        is_method: Whether the function is a method of a class
        is_property: Whether the function is a property of a class
        is_static: Whether the function is a static method of a class
        line_number: The line number the function is defined in
        name: The name of the function
        raises: The (potentially empty) set of exceptions the function raises
        raises_assert: Whether the function raises any exceptions
        return_type: The annotated type the function returns (if any)
        return_value: The return node from the AST (if any)
        variables: A list of variables that get defined inside the function
    """

    argument_names: list[str]
    argument_types: list[tuple[str, str | None]]
    docstring: str | None
    func: ast.AsyncFunctionDef | ast.FunctionDef
    has_empty_return: bool
    has_return: bool
    has_yield: bool
    is_abstract: bool | None
    is_method: bool
    is_property: bool
    is_static: bool
    line_number: int
    name: str
    raises: set[str]
    raises_assert: bool
    return_type: str | None
    return_value: ast.Return | None
    variables: list[ast.Name]


def get_function_descriptions(program: ast.AST) -> list[FunctionDescription]:
    """Extracts the function descriptions from the AST.

    Args:
        program: The program's AST

    Returns:
        A list of function descriptions extracted from the AST
    """
    result: list[FunctionDescription] = []
    functions_methods = FunctionAndMethodVisitor()
    functions_methods.visit(program)
    for prop in functions_methods.properties:
        result.append(
            __build_function_description(function_type=FunctionType.PROPERTY, func=prop)
        )
    for method in functions_methods.methods:
        result.append(
            __build_function_description(function_type=FunctionType.METHOD, func=method)
        )
    for function in functions_methods.functions:
        result.append(
            __build_function_description(
                function_type=FunctionType.FUNCTION, func=function
            )
        )
    return result


def __build_function_description(
    function_type: FunctionType, func: ast.AsyncFunctionDef | ast.FunctionDef
) -> FunctionDescription:
    function_analysis = FunctionAnalysisVisitor()
    function_analysis.visit(func)

    arguments = function_analysis.arguments
    argument_types = function_analysis.types
    if function_type != FunctionType.FUNCTION and len(arguments) > 0:
        if not has_decorator(func, "staticmethod"):
            arguments.pop(0)
            argument_types.pop(0)

    has_return = bool(function_analysis.returns)
    has_empty_return = False
    return_value = None
    if has_return:
        return_value = function_analysis.returns[0]
        has_empty_return = return_value is not None and return_value.value is None

    return FunctionDescription(
        argument_names=arguments,
        argument_types=argument_types,
        docstring=get_docstring(func),
        func=func,
        has_empty_return=has_empty_return,
        has_return=has_return,
        has_yield=bool(function_analysis.yields),
        is_abstract=function_analysis.is_abstract,
        is_method=(function_type == FunctionType.METHOD),
        is_property=(function_type == FunctionType.PROPERTY),
        is_static=function_analysis.is_static,
        line_number=get_line_number_for_function(func),
        name=func.name,
        raises=function_analysis.exceptions,
        raises_assert=bool(function_analysis.asserts),
        return_type=get_return_type(func),
        return_value=return_value,
        variables=function_analysis.variables,
    )
