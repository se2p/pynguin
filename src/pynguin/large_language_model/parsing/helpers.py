# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Helper function for LLM parser."""

import ast
import logging

import pynguin.testcase.testcase as tc
import pynguin.testcase.testcase_to_ast as tta
import pynguin.utils.namingscope as ns


logger = logging.getLogger(__name__)


def _count_all_statements(node) -> int:
    """Counts statements.

    Counts the number of statements in node and all blocks, not including `node`

    Args:
        node: node to count statements for.

    Returns:
        the number of child statements to node.
    """
    num_non_assert_statements = 0
    for _, value in ast.iter_fields(node):
        # For all blocks
        if isinstance(value, list) and all(isinstance(elem, ast.stmt) for elem in value):
            for elem in value:
                if isinstance(elem, ast.Assert):
                    continue
                num_non_assert_statements += 1
                num_non_assert_statements += _count_all_statements(elem)
    return num_non_assert_statements


def key_in_dict(value, d):
    """Turns out that `True in {1: 2}` returns True!

    Args:
        value: a key
        d: a dictionary

    Returns:
        true is `value` is actually in the keys of `d`
    """
    if isinstance(value, bool):
        return any(k is value for k in d)
    return value in d


def has_bound_variables(node: ast.AST, bound_variables: set[str]) -> bool:
    """Returns true if node has references to the variables in `bound_variables`.

    Args:
        node: the node to visit
        bound_variables: the set of variables which are bound

    Returns:
        true if node has references to the variables in `bound_variables`.
    """

    class BoundVariableVisitor(ast.NodeVisitor):
        """Helper class that identifies if any names are in `bound_variables`."""

        def __init__(self):
            self.has_bound_variable = False

        def visit_Name(self, node: ast.Name):  # noqa: N802
            if node.id in bound_variables:
                self.has_bound_variable = True

    bound_variable_visitor = BoundVariableVisitor()
    bound_variable_visitor.visit(node)
    return bound_variable_visitor.has_bound_variable


def has_call(node: ast.AST):
    """Returns true if node is it has descendant nodes that are calls.

    Args:
        node: an ast Node

    Returns:
        Whether node has a call in one of its descendant
    """

    class CallFinder(ast.NodeVisitor):
        def __init__(self):
            super().__init__()
            self.has_call = False

        def visit_Call(self, call: ast.Call):  # noqa: N802
            self.has_call = True

    finder = CallFinder()
    finder.visit(node)
    return finder.has_call


def is_expr_or_stmt(node: ast.AST):
    """Whether node is an expression or statement.

     i.e. whether it potentially has useful children to recurse into.
     this excludes constants like ast.Load, ast.Store.

    Args:
        node: an ast Node

    Returns:
        Whether node is an expression or statement
    """
    return isinstance(node, ast.expr | ast.stmt)


def unparse_test_case(test_case: tc.TestCase) -> str | None:
    """Convert a test case to its AST representation as a string.

    Args:
        test_case (tc.TestCase): The test case to convert.

    Returns:
        str | None: The Python code as a string, or None if an error occurs.
    """
    naming = ns.NamingScope("module")

    visitor = tta.TestCaseToAstVisitor(
        module_aliases=naming, common_modules=set(), store_call_return=True
    )
    try:
        test_case.accept(visitor)
        test_case_ast = visitor.test_case_ast

        func_def = ast.FunctionDef(
            name="test_generated_function",
            args=ast.arguments(
                posonlyargs=[],
                args=[],
                vararg=None,
                kwonlyargs=[],
                kw_defaults=[],
                kwarg=None,
                defaults=[],
            ),
            body=test_case_ast,
            decorator_list=[],
        )

        # Wrap the function definition in an ast.Module
        module_node = ast.Module(body=[func_def], type_ignores=[])
        ast.fix_missing_locations(module_node)

        # Ensure the module node is valid
        if not isinstance(module_node, ast.Module):
            raise ValueError("The module node is not valid.")

        return ast.unparse(module_node)
    except BaseException as e:  # noqa: BLE001
        logger.error("Error processing test case AST: %s", e)
        return None
