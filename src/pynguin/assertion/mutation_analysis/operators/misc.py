#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides miscellaneous operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/misc.py
and https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/utils.py
and integrated in Pynguin.
"""

import ast
import sys

from pynguin.assertion.mutation_analysis.operators.arithmetic import (
    AbstractArithmeticOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, copy_node


def is_docstring(node: ast.AST) -> bool:
    """Check if the given node is a docstring.

    Args:
        node: The node to check.

    Returns:
        True if the node is a docstring, False otherwise.
    """
    if sys.version_info >= (3, 14):
        correct_type = ast.Constant
    else:
        correct_type = ast.Str
    if not isinstance(node, correct_type):
        return False

    expression_node: ast.AST = node.parent  # type: ignore[attr-defined]

    if not isinstance(expression_node, ast.Expr):
        return False

    def_node: ast.AST = expression_node.parent  # type: ignore[attr-defined]

    return (
        isinstance(def_node, ast.FunctionDef | ast.ClassDef | ast.Module)
        and def_node.body  # type: ignore[return-value]
        and def_node.body[0] == expression_node
    )


_UNOBSERVABLE_CALL_NAMES = frozenset({
    "print",
    "debug",
    "info",
    "warning",
    "warn",
    "error",
    "exception",
    "critical",
    "log",
})


def is_unobservable_string_context(node: ast.AST) -> bool:
    """Check if a string-valued node can never be observed by an assertion.

    Strings that only serve as exception messages or as arguments to logging
    or printing calls cannot be checked by the generated assertions: exception
    assertions only record the exception type, and log or print output is not
    captured at all. Mutants in such positions are unkillable and only dilute
    the mutation score.

    Args:
        node: The node to check.

    Returns:
        True if the node's value is unobservable, False otherwise.
    """
    current: ast.AST | None = getattr(node, "parent", None)
    while current is not None and not isinstance(current, ast.stmt):
        if isinstance(current, ast.Call):
            func = current.func
            name: str | None = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name in _UNOBSERVABLE_CALL_NAMES:
                return True
        current = getattr(current, "parent", None)
    return isinstance(current, ast.Raise)


class AssignmentOperatorReplacement(AbstractArithmeticOperatorReplacement):
    """A class that mutates assignment operators by replacing them."""

    def should_mutate(self, node: ast.AST) -> bool:  # noqa: D102
        parent = node.parent  # type: ignore[attr-defined]
        return isinstance(parent, ast.AugAssign)


class BreakContinueReplacement(MutationOperator):
    """A class that mutates break and continue statements by replacing them."""

    def mutate_Break(self, node: ast.Break) -> ast.Continue:  # noqa: N802
        """Mutate a Break statement to a Continue statement.

        Args:
            node: The Break statement to mutate.

        Returns:
            The mutated statement.
        """
        return ast.Continue()

    def mutate_Break_to_return(self, node: ast.Break) -> ast.Return:  # noqa: N802
        """Mutate a Break statement to a Return statement.

        Args:
            node: The Break statement to mutate.

        Returns:
            The mutated statement.
        """
        return ast.Return(value=None)

    def mutate_Continue(self, node: ast.Continue) -> ast.Break:  # noqa: N802
        """Mutate a Continue statement to a Break statement.

        Args:
            node: The Continue statement to mutate.

        Returns:
            The mutated statement.
        """
        return ast.Break()


class ConstantReplacement(MutationOperator):
    """A class that mutates constants by replacing them."""

    FIRST_CONST_STRING = "mutpy"
    SECOND_CONST_STRING = "python"

    def help_str(self, node: ast.Constant) -> str | None:
        """Help function for mutating strings.

        Args:
            node: The string to mutate.

        Returns:
            The mutated string, or None if the string should not be mutated.
        """
        if is_docstring(node) or is_unobservable_string_context(node):
            return None

        if node.value == self.FIRST_CONST_STRING:
            return self.SECOND_CONST_STRING

        return self.FIRST_CONST_STRING

    @staticmethod
    def help_str_empty(node: ast.Constant) -> str | None:
        """Help function for mutating empty strings.

        Args:
            node: The string to mutate.

        Returns:
            The mutated string, or None if the string should not be mutated.
        """
        if not node.value or is_docstring(node) or is_unobservable_string_context(node):
            return None

        return ""

    def mutate_Constant_num(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a numeric constant by adding 1.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        value = node.value

        if not isinstance(value, int | float) or isinstance(value, bool):
            return None

        return ast.Constant(value + 1)

    def mutate_Constant_num_decrement(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a numeric constant by subtracting 1.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated
            or the result would duplicate the zero replacement.
        """
        value = node.value

        if not isinstance(value, int | float) or isinstance(value, bool):
            return None

        if value == 1:
            return None

        return ast.Constant(value - 1)

    def mutate_Constant_str(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a string constant by replacing it.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        if not isinstance(node.value, str):
            return None

        new_value = self.help_str(node)

        if new_value is None:
            return None

        return ast.Constant(new_value)

    def mutate_Constant_str_empty(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate an empty string constant by replacing it.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        if not isinstance(node.value, str):
            return None

        new_value = self.help_str_empty(node)

        if new_value is None:
            return None

        return ast.Constant(new_value)

    def mutate_Constant_num_zero(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a numeric constant by replacing it with zero.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        value = node.value
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        if value == 0:
            return None
        return ast.Constant(0)

    def mutate_Constant_num_neg(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a numeric constant by negating it.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        value = node.value
        if not isinstance(value, int | float) or isinstance(value, bool):
            return None
        if value == 0:
            return None
        return ast.Constant(-value)


class SliceIndexRemove(MutationOperator):
    """A class that mutates slice indices by removing them."""

    def mutate_Slice_remove_lower(  # noqa: N802
        self, node: ast.Slice
    ) -> ast.Slice | None:
        """Mutate a Slice index by removing the lower bound.

        Args:
            node: The Slice index to mutate.

        Returns:
            The mutated index, or None if the index should not be mutated.
        """
        if node.lower is None:
            return None

        return ast.Slice(lower=None, upper=node.upper, step=node.step)

    def mutate_Slice_remove_upper(  # noqa: N802
        self, node: ast.Slice
    ) -> ast.Slice | None:
        """Mutate a Slice index by removing the upper bound.

        Args:
            node: The Slice index to mutate.

        Returns:
            The mutated index, or None if the index should not be mutated.
        """
        if node.upper is None:
            return None

        return ast.Slice(lower=node.lower, upper=None, step=node.step)

    def mutate_Slice_remove_step(  # noqa: N802
        self, node: ast.Slice
    ) -> ast.Slice | None:
        """Mutate a Slice index by removing the step.

        Args:
            node: The Slice index to mutate.

        Returns:
            The mutated index, or None if the index should not be mutated.
        """
        if node.step is None:
            return None

        return ast.Slice(lower=node.lower, upper=node.upper, step=None)


class BooleanLiteralReplacement(MutationOperator):
    """A class that mutates boolean literals by replacing them."""

    def mutate_Constant_bool(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a boolean literal by negating it.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        if not isinstance(node.value, bool):
            return None
        return ast.Constant(not node.value)


class LambdaReplacement(MutationOperator):
    """A class that mutates lambda expressions by replacing their body with None."""

    def mutate_Lambda(self, node: ast.Lambda) -> ast.Lambda | None:  # noqa: N802
        """Mutate a lambda expression by replacing its body with None.

        Args:
            node: The lambda expression to mutate.

        Returns:
            The mutated expression, or None if the body is already None.
        """
        if isinstance(node.body, ast.Constant) and node.body.value is None:
            return None
        mutated = copy_node(node)
        mutated.body = ast.Constant(value=None)
        return mutated


class FStringReplacement(MutationOperator):
    """A class that mutates f-strings by replacing them with a plain string."""

    REPLACEMENT_STRING = "mutpy"

    def mutate_JoinedStr(  # noqa: N802
        self, node: ast.JoinedStr
    ) -> ast.Constant | None:
        """Mutate an f-string by replacing it with a plain string constant.

        Args:
            node: The f-string to mutate.

        Returns:
            The mutated node, or None if the f-string is a format specification
            of another f-string or its value cannot be observed by an assertion.
        """
        parent = node.parent  # type: ignore[attr-defined]

        if isinstance(parent, ast.FormattedValue):
            return None

        if is_unobservable_string_context(node):
            return None

        return ast.Constant(value=self.REPLACEMENT_STRING)


class AssignmentValueReplacement(MutationOperator):
    """A class that mutates assignments by replacing their value with None."""

    def mutate_Assign(self, node: ast.Assign) -> ast.Assign | None:  # noqa: N802
        """Mutate an assignment by replacing its value with None.

        Args:
            node: The assignment to mutate.

        Returns:
            The mutated assignment, or None if the value is already None.
        """
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            return None
        mutated = copy_node(node)
        mutated.value = ast.Constant(value=None)
        return mutated
