#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Targeted unit tests for the remaining uncovered edges of ``testcase.py``."""

import libcst as cst
import pytest

import pynguin.testcase.testcase as tc
from tests.testcase._builders import assign, int_stmt, make_test_case, stmt, str_stmt


def test_uses_variable_module_function():
    """Covers the private ``_uses_variable`` helper (currently dead code)."""
    statement = stmt("x = foo(y)", bound_variable="x")

    assert tc._uses_variable(statement, "y") is True
    assert tc._uses_variable(statement, "z") is False


def test_clone_is_deep_copy_and_independent():
    original = make_test_case(
        int_stmt("var_0", 1),
        assign("var_1", "var_0 + 1", bound_type=int),
    )
    original.get_statement(0).assertions.append("marker")  # type: ignore[arg-type]

    cloned = original.clone()

    # Cloned statements are distinct objects with independently-owned lists.
    assert cloned.get_statement(0) is not original.get_statement(0)
    assert cloned.get_statement(0).assertions == original.get_statement(0).assertions
    assert cloned.get_statement(0).assertions is not original.get_statement(0).assertions

    # Mutating the clone does not affect the original.
    cloned.add_statement(int_stmt("var_2", 42))
    assert cloned.size() == 3
    assert original.size() == 2

    # Mutating the original after cloning does not affect the clone.
    original.get_statement(0).assertions.append("other")  # type: ignore[arg-type]
    assert "other" not in cloned.get_statement(0).assertions

    assert cloned.to_code() != original.to_code()


@pytest.mark.parametrize(
    ("position", "expected_size"),
    [
        (-1, 0),
        (1, 2),
    ],
)
def test_chop(position, expected_size):
    test_case = make_test_case(
        int_stmt("var_0", 1),
        int_stmt("var_1", 2),
        int_stmt("var_2", 3),
    )

    test_case.chop(position)

    assert test_case.size() == expected_size


def test_forward_dependencies_transitive_closure():
    # var_0 taints stmt1 (uses var_0, binds var_1), which transitively taints
    # stmt2 (uses var_1 only, not var_0 directly).
    test_case = make_test_case(
        int_stmt("var_0", 1),
        assign("var_1", "var_0 + 1", bound_type=int),
        assign("var_2", "var_1 + 1", bound_type=int),
        int_stmt("var_3", 99),
    )

    assert test_case.forward_dependencies(0) == {0, 1, 2}


def test_remove_statement_updates_registry():
    test_case = make_test_case(
        int_stmt("var_0", 1),
        str_stmt("var_1", "hello"),
        int_stmt("var_2", 2),
    )

    removed = test_case.remove_statement(1)

    assert removed.bound_variable == "var_1"
    assert test_case.size() == 2
    assert "var_1" not in test_case.variables_of_type(str)
    assert test_case.variables_of_type(int) == ["var_0", "var_2"]


def test_remove_unused_variables_transforms_unused_assign_and_keeps_used():
    test_case = make_test_case(
        int_stmt("var_0", 1),  # unused later -> transformed to Expr
        int_stmt("var_1", 2),  # used later -> kept as Assign
        assign("var_2", "var_1 + 1", bound_type=int),
    )

    test_case.remove_unused_variables()

    assert test_case.get_statement(0).bound_variable is None
    assert "var_0" not in test_case.to_code()
    assert test_case.get_statement(1).bound_variable == "var_1"
    assert "var_1 = 2" in test_case.to_code()


def test_transform_assign_to_expr_edge_cases_leave_node_unchanged():
    # A bound variable on a compound statement (not a SimpleStatementLine) cannot
    # be transformed to an Expr and must be returned unchanged.
    compound = stmt("if True:\n    pass\n", bound_variable="unused_compound", bound_type=None)
    # A chained assignment has more than one target, so it is not eligible for
    # the Assign -> Expr transform either; it must also come back unchanged.
    chained = stmt("chained_a = chained_b = 1", bound_variable="chained_a", bound_type=int)

    test_case = make_test_case(compound, chained)

    original_compound_node = test_case.get_statement(0).node
    original_chained_node = test_case.get_statement(1).node

    test_case.remove_unused_variables()

    assert test_case.get_statement(0).node is original_compound_node
    assert test_case.get_statement(0).bound_variable == "unused_compound"
    assert test_case.get_statement(1).node is original_chained_node
    assert test_case.get_statement(1).bound_variable == "chained_a"


def test_eq_returns_not_implemented_for_non_testcase():
    test_case = make_test_case(int_stmt("var_0", 1))

    assert (test_case == 42) is False
    assert test_case != 42


def test_to_test_function_wraps_statements_and_handles_empty_case():
    test_case = make_test_case(int_stmt("var_0", 1))

    module = test_case.to_test_function(index=3)

    assert isinstance(module, cst.Module)
    func = module.body[0]
    assert isinstance(func, cst.FunctionDef)
    assert func.name.value == "test_3"
    assert "var_0 = 1" in module.code

    empty_module = tc.TestCase().to_test_function()
    empty_func = empty_module.body[0]
    assert isinstance(empty_func, cst.FunctionDef)
    assert "pass" in empty_module.code


def test_append_test_case_from_resolves_head_reference_and_drops_unsatisfiable():
    self_tc = make_test_case(int_stmt("existing_int", 1))

    other = make_test_case(
        int_stmt("h", 1),  # head, index 0 (int)
        str_stmt("h2", "x"),  # head, index 1 (str) -- no candidate in self_tc
        assign("new_var", "h + 1", bound_type=int),  # index 2: resolvable via rename
        assign("bad", "h2 + 'y'", bound_type=str),  # index 3: unsatisfiable -> dropped
        assign("dependent", "bad + 'z'", bound_type=str),  # index 4: depends on dropped
    )

    self_tc.append_test_case_from(other, 2)

    # Only the resolvable statement was appended; the unsatisfiable one and its
    # dependent were dropped.
    assert self_tc.size() == 2
    appended = self_tc.get_statement(1)
    assert appended.bound_variable is not None
    assert appended.bound_variable != "new_var"  # renamed to a fresh var name
    code = self_tc.to_code()
    assert "existing_int + 1" in code
    assert "h + 1" not in code
    assert "bad" not in code
    assert "dependent" not in code
