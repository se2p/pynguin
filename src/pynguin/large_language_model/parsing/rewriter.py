# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
# SPDX-FileCopyrightText: 2023 Microsoft
#
# SPDX-License-Identifier: MIT
#
"""Holds logic for rewriting code generated by LLM into a format closer to Pynguin's.

The logic is adapted from the CodaMosa repository with additional refactoring.
https://github.com/microsoft/codamosa
"""

import ast
import logging
import re

from typing import Any

from pynguin.large_language_model.parsing.helpers import has_bound_variables
from pynguin.large_language_model.parsing.helpers import has_call
from pynguin.large_language_model.parsing.helpers import is_expr_or_stmt
from pynguin.large_language_model.parsing.helpers import key_in_dict


logger = logging.getLogger(__name__)


class StmtRewriter(ast.NodeTransformer):  # noqa: PLR0904
    """Rewrites a statement as much as possible.

    - If it can be rewritten as an assignment statement, write it as an assignment.
    - Each child expression of the expression on the statement's RHS is rewritten,
      so it is a variable reference, and a variable assignment is added defining
      that variable to the correct expression.

    Exceptions:
        - Currently don't recurse into function definitions or lambdas.
        - Call expressions are allowed to have a single-level attribute
          expression as the function being called.
    """

    def __init__(self):  # noqa: D107
        self.stmts_to_add: list[ast.stmt] = []
        # We don't track this in e.g. function calls because there
        # are no scoping issues in extracting subexpressions there
        self._bound_variables: set[str] = set()
        self.replace_only_free_subnodes = False

        self._bound_variables_stack: list[set[str]] = []
        self._replace_only_free_stack: list[bool] = []

        # State that matters for block-level scoping
        self.used_varnames: set[str] = set()
        self.var_counter = 0
        self.constant_dict = {}
        self.used_varnames_stack: list[set[str]] = []
        self.var_counter_stack: list[int] = []
        self.constant_dict_stack: list[dict[Any, ast.Name]] = []
        super().__init__()

    def reset_stmts_to_add(self):
        """Call after visit to avoid adding redundant statements."""
        self.stmts_to_add = []

    def generate_new_varname(self):
        """Get a fresh variable name in format var_X.

        Returns:
            a new variable name.
        """
        new_varname = "var_" + str(self.var_counter)
        self.var_counter += 1
        while new_varname in self.used_varnames:
            new_varname = "var_" + str(self.var_counter)
            self.var_counter += 1
        self.used_varnames.add(new_varname)
        return new_varname

    def replace_with_varname(self, node):
        """Returns an ast.Name node.

         To replace `node` with, or no-op if `node` is already a name.

        Args:
            node: an ast Node.

        Returns:
            an ast.Name node to replace `node` with.
        """
        if isinstance(node, ast.Name):
            return node
        if isinstance(node, ast.Constant) and key_in_dict(node.value, self.constant_dict):
            varname = self.constant_dict[node.value]
        elif self.replace_only_free_subnodes and has_bound_variables(node, self._bound_variables):
            return node
        else:
            varname = self.generate_new_varname()
            if isinstance(node, ast.Constant):
                self.constant_dict[node.value] = varname
            assign_decl = ast.Assign(targets=[ast.Name(varname, ctx=ast.Store())], value=node)
            self.stmts_to_add.append(assign_decl)

        return ast.Name(varname, ctx=ast.Load())

    def enter_new_block_scope(self):
        """Call when entering a new variable name scope."""
        self.used_varnames_stack.append(self.used_varnames)
        self.var_counter_stack.append(self.var_counter)
        self.constant_dict_stack.append(self.constant_dict)
        self.used_varnames = set()
        self.var_counter = 0
        self.constant_dict = {}

    def exit_block_scope(self):
        """Call when exiting a new variable name scope."""
        self.used_varnames = self.used_varnames_stack.pop()
        self.var_counter = self.var_counter_stack.pop()
        self.constant_dict = self.constant_dict_stack.pop()

    def enter_new_bound_scope(self):
        """Call when visiting an expression that creates new bound vars."""
        self._bound_variables_stack.append(set(self._bound_variables))
        self._replace_only_free_stack.append(self.replace_only_free_subnodes)
        self.replace_only_free_subnodes = True

    def exit_bound_scope(self):
        """Call when done visiting an expression that creates new bound vars."""
        self._bound_variables = self._bound_variables_stack.pop()
        self.replace_only_free_subnodes = self._replace_only_free_stack.pop()

    def get_stmts_to_add(self):
        """Get all the assignment statements that were created while visiting.

        Returns:
            the statements that were added during the visit.
        """
        return self.stmts_to_add

    def visit_block_helper(self, block: list[ast.stmt]):
        """Helper to visit a list of statements, as in a function body.

        Args:
            block: the body to visit.

        Returns:
            a list of ast statements.
        """
        self.enter_new_block_scope()
        new_body = []
        for stmt in block:
            new_stmt = self.visit(stmt)
            new_body.extend(self.get_stmts_to_add())
            self.reset_stmts_to_add()
            if new_stmt is not None:
                new_body.append(new_stmt)
        self.exit_block_scope()
        return new_body

    def generic_visit(self, node):
        """A generic visit.

        Returns an ast node of the same type as `node`, but with any ast.AST
        nodes replaced with ast.Name nodes.

        The core difference with the standard generic_visitor is that nodes
        are replaced with var names after visiting.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        field_assign = {}
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                new_value_lst = []
                for item in value:
                    if is_expr_or_stmt(item):
                        new_item = self.visit(item)
                        item_name = self.replace_with_varname(new_item)
                        new_value_lst.append(item_name)
                    else:
                        new_value_lst.append(item)
                field_assign[field] = new_value_lst
            elif is_expr_or_stmt(value):
                new_value = self.visit(value)
                value_name = self.replace_with_varname(new_value)
                field_assign[field] = value_name
            else:
                field_assign[field] = value
        return node.__class__(**field_assign)

    def visit_only_calls_subnodes(self, node):
        """Same as above but only visits subnodes which contain function calls.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        field_assign = {}
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                new_value_lst = []
                for item in value:
                    if is_expr_or_stmt(item) and has_call(item):
                        new_item = self.visit(item)
                        item_name = self.replace_with_varname(new_item)
                        new_value_lst.append(item_name)
                    else:
                        new_value_lst.append(item)
                field_assign[field] = new_value_lst
            elif is_expr_or_stmt(value) and has_call(value):
                new_value = self.visit(value)
                value_name = self.replace_with_varname(new_value)
                field_assign[field] = value_name
            else:
                field_assign[field] = value
        return node.__class__(**field_assign)

    def visit_Call(self, call: ast.Call):  # noqa: N802
        """Visit a call.

        When visiting a call expression, allow the callee to be
        an ast.Attribute of one level, i.e. q.foo().

        Args:
            call: the call node to visit.

        Returns:
            the transformed node.
        """
        func = self.visit(call.func)
        if not isinstance(func, ast.Attribute):
            func = self.replace_with_varname(func)
        new_args = []
        for arg in call.args:
            if isinstance(arg, ast.Starred):
                new_args.append(self.visit(arg))
            else:
                arg_value = self.visit(arg)
                new_args.append(self.replace_with_varname(arg_value))
        new_kwargs = []
        for kwarg in call.keywords:
            kwarg_value = self.visit(kwarg.value)
            kwarg_value = self.replace_with_varname(kwarg_value)
            new_kwargs.append(ast.keyword(arg=kwarg.arg, value=kwarg_value))

        return ast.Call(func=func, args=new_args, keywords=new_kwargs)

    def visit_Subscript(self, subscript: ast.Subscript):  # noqa: N802
        """Subscripts can be both element accesses in a list, or a parameterization.

        Don't separate the LHS into its own variable if it's an attribute reference.

        Args:
            subscript: the subscript node to visit.

        Returns:
            the transformed node.
        """
        if isinstance(subscript.slice, ast.Tuple):
            new_slice_elts = []
            for elem in subscript.slice.elts:
                new_elem = self.visit(elem)
                if isinstance(elem, ast.Slice):
                    new_slice_elts.append(new_elem)
                else:
                    new_slice_elts.append(self.replace_with_varname(new_elem))
            new_slice = ast.Tuple(elts=new_slice_elts, ctx=ast.Load())
        elif isinstance(subscript.slice, ast.Slice):
            new_slice = self.visit(subscript.slice)
        else:
            new_slice = self.visit(subscript.slice)
            new_slice = self.replace_with_varname(new_slice)

        new_value = self.visit(subscript.value)

        return ast.Subscript(value=new_value, slice=new_slice, ctx=subscript.ctx)

    def visit_UnaryOp(self, node):  # noqa: N802
        """Visits unary op."""
        if isinstance(node.operand, ast.Constant):
            return node
        return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:  # noqa: N802
        """When visiting attribute nodes, keep repeated dereferences.

         If they are just attribute/field accesses, but separate calls
        into their own functions. This may get us into trouble with separating
        out field/property accesses, but it saves us from stripping out modules
        into variables.

        E.g.
            typed_ast._ast3.parse(var_0) should not be transformed
            ast_0.fix_stuff().foo() should have ast_0.fix_stuff() put into a new var

        Args:
            node: the attribute node to visit.

        Returns:
            the transformed node.
        """
        if isinstance(node.value, ast.Name) and node.value.id == "self":
            return self.replace_with_varname(ast.Name(id=node.attr, ctx=node.ctx))

        value_visited = self.visit(node.value)
        if isinstance(node.value, ast.Attribute):
            node.value = value_visited
        else:
            node.value = self.replace_with_varname(value_visited)
        return node

    def visit_Assign(self, assign: ast.Assign):  # noqa: N802
        """When visiting an assignment statement.

         The right hand side expression does not need to become
         a variable reference.

        Args:
            assign: the assign node to visit.

        Returns:
            the transformed node.
        """
        for target in assign.targets:
            if isinstance(target, ast.Name):
                self.used_varnames.add(target.id)
        new_rhs = self.visit(assign.value)
        return ast.Assign(targets=assign.targets, value=new_rhs, type_comment=assign.type_comment)

    def visit_AnnAssign(self, node: ast.AnnAssign):  # noqa: N802
        """Convert annotated assigns as well to the correct format.

         but stripping their type annotations.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        if node.value is not None:
            return self.visit(ast.Assign(targets=[node.target], value=node.value))
        return None

    def visit_AugAssign(self, node):  # noqa: N802
        """Convert augmented assigns to regular assigns.

        Right now `statement_deserializer` wouldn't support the
        operations on the RHS anyway, but worth a try.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        new_aug_assign = self.generic_visit(node)
        rhs_binop = ast.BinOp(
            left=new_aug_assign.target, op=new_aug_assign.op, right=new_aug_assign.value
        )
        return ast.Assign(targets=[new_aug_assign.target], value=rhs_binop)

    def visit_NamedExpr(self, node: ast.NamedExpr):  # noqa: N802
        """Transform walrus expressions to regular assigns + uses (x := 3).

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        rhs = self.visit(node.value)
        self.stmts_to_add.append(ast.Assign(targets=[node.target], value=rhs))
        return node.target

    def visit_Expr(self, expr: ast.Expr):  # noqa: N802
        """A standalone ast.Expr node is an expression as statement.

        The value field stores the actual expr object. Again,
        we don't want to replace that whole expression with a variable reference,
        instead create an assignment statement to contain the expr.

        Args:
            expr: the node to visit.

        Returns:
            the transformed node.
        """
        if isinstance(expr.value, ast.NamedExpr):
            rhs = self.visit(expr.value.value)
            return ast.Assign(targets=[expr.value.target], value=rhs)
        # Don't mess with awaits/yields
        if type(expr.value) in {ast.Await, ast.Yield, ast.YieldFrom}:
            return expr
        rhs = self.visit(expr.value)
        return ast.Assign(targets=[ast.Name(id=self.generate_new_varname())], value=rhs)

    def visit_Assert(self, assert_node: ast.Assert):  # noqa: N802
        """We want the test's upper level comparators to remain.

        But extract the sub-expressions into variables when they contain calls.

        Args:
            assert_node: the node to visit.

        Returns:
            the transformed node.
        """
        if isinstance(assert_node.test, ast.Call):
            return self.generic_visit(assert_node)
        new_test = self.visit_only_calls_subnodes(assert_node.test)
        return ast.Assert(new_test)

    def visit_FunctionDef(self, fn_def_node: ast.FunctionDef):  # noqa: N802
        """Reformat the test in fn_def_node.

         so it can be parsed by initial population seeding module.

        Args:
            fn_def_node: the node to visit.

        Returns:
            the transformed node.
        """
        if not fn_def_node.name.startswith("test_"):
            return fn_def_node

        fn_def_node.args.args = [arg for arg in fn_def_node.args.args if arg.arg != "self"]
        # Visit the main body
        new_body = self.visit_block_helper(fn_def_node.body)
        fn_def_node.body = new_body
        ast.fix_missing_locations(fn_def_node)

        return fn_def_node

    def visit_ClassDef(self, node: ast.ClassDef):  # noqa: N802
        """Transform the class by filtering and taking only test methods.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        if any(
            isinstance(stmt, ast.FunctionDef) and stmt.name.startswith("test_")
            for stmt in node.body
        ):
            new_body = []
            for stmt in node.body:
                if isinstance(stmt, ast.FunctionDef) and stmt.name.startswith("test_"):
                    new_body.append(rewrite_test(stmt))
                else:
                    new_body.append(stmt)
            return ast.ClassDef(
                name=node.name,
                bases=node.bases,
                keywords=node.keywords,
                body=new_body,
                decorator_list=node.decorator_list,
            )
        return node

    def visit_For(self, node):  # noqa: N802
        """Visit a for loop node and transform its body and orelse.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        return node

    def visit_While(self, node: ast.While):  # noqa: N802
        """Visit a while loop node and transform its body and orelse.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        return node

    def visit_If(self, node):  # noqa: N802
        """Visit an if statement node and transform its body and orelse.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        return node

    def visit_With(self, node):  # noqa: N802
        """Visit a with statement node and transform its body.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        node.body = self.visit_block_helper(node.body)
        return node

    def visit_Try(self, node: ast.Try):  # noqa: N802
        """Visit a try statement node and transform its body, orelse, and finalbody.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        node.finalbody = self.visit_block_helper(node.finalbody)
        return node

    def visit_Lambda(self, node: ast.Lambda):  # noqa: N802
        """Visit a lambda node and transform its body.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        self.enter_new_bound_scope()
        all_args: ast.arguments = node.args
        for arg in all_args.args + all_args.kwonlyargs:
            arg_name = arg.arg
            self._bound_variables.add(arg_name)
        if all_args.kwarg is not None:
            self._bound_variables.add(all_args.kwarg.arg)
        if all_args.vararg is not None:
            self._bound_variables.add(all_args.vararg.arg)
        new_lambda = self.generic_visit(node)
        self.exit_bound_scope()
        return new_lambda

    def get_comprehension_bound_vars(self, node: ast.comprehension) -> list[str]:
        """Get the bound variables for a comprehension node.

        Args:
            node: the node to visit.

        Returns:
            a list of bound variable names.
        """
        return [elem.id for elem in ast.walk(node.target) if isinstance(elem, ast.Name)]

    def _visit_generators_common(self, generators: list[ast.comprehension]):
        """Common logic for visiting comprehension generators.

        Args:
            generators: a list of comprehension nodes.

        Returns:
            a list of transformed comprehension nodes.
        """
        new_generators = []
        for comp in generators:
            self._bound_variables.update(self.get_comprehension_bound_vars(comp))
            new_generators.append(self.visit(comp))
        return new_generators

    def visit_GeneratorExp(  # noqa: N802
        self, node: ast.GeneratorExp
    ) -> ast.GeneratorExp:
        """Visit a generator expression node and transform its body.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.GeneratorExp(elt=new_elt, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    def visit_ListComp(self, node: ast.ListComp) -> ast.ListComp:  # noqa: N802
        """Visit a list comprehension node and transform its body.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.ListComp(elt=new_elt, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    def visit_SetComp(self, node: ast.SetComp) -> ast.SetComp:  # noqa: N802
        """Visit a set comprehension node and transform its body.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.SetComp(elt=new_elt, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    def visit_DictComp(self, node: ast.DictComp) -> ast.DictComp:  # noqa: N802
        """Visit a dict comprehension node and transform its body.

        Args:
            node: the node to visit.

        Returns:
            the transformed node.
        """
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_key = self.visit(node.key)
        new_value = self.visit(node.value)
        ret_val = ast.DictComp(key=new_key, value=new_value, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    def visit_Import(self, node):  # noqa: N802
        """Visit an import statement node.

        Args:
            node: the node to visit.

        Returns:
            the original node.
        """
        return node

    def visit_ImportFrom(self, node):  # noqa: N802
        """Visit an import from statement node.

        Args:
            node: the node to visit.

        Returns:
            the original node.
        """
        return node

    def visit_Await(self, node):  # noqa: N802
        """Visit an await statement node.

        Args:
            node: the node to visit.

        Returns:
            the original node.
        """
        return node

    def visit_AsyncFunctionDef(self, node):  # noqa: N802
        """Visit an async function definition node.

        Args:
            node: the node to visit.

        Returns:
            the original node.
        """
        return node

    def visit_AsyncFor(self, node):  # noqa: N802
        """Visit an async for statement node.

        Args:
            node: the node to visit.

        Returns:
            the original node.
        """
        return node

    def visit_AsyncWith(self, node):  # noqa: N802
        """Visit an async with statement node.

        Args:
            node: the node to visit.

        Returns:
            the original node.
        """
        return node

    def visit_Match(self, node):  # noqa: N802
        """Visit a match statement node.

        Args:
            node: the node to visit.

        Returns:
            the original node.
        """
        return node


def rewrite_tests(source: str) -> dict[str, str]:
    """Rewrite the tests in `source` so that they can be parsed.

    By AstToTestCaseTransformer.

    Args:
        source: the source code containing tests.

    Returns:
        a dictionary with function names as keys and rewritten tests as values.
    """
    # Sometimes LLM returns function definition with only a comment inside
    # which results in syntax error.
    empty_function_pattern = re.compile(
        r"^\s*def\s+\w+\s*\(.*\):\s*\n\s*#.*?\n(?:\s*\n)*(?=^\s*def|\Z)", re.MULTILINE
    )
    source_without_empty_methods = re.sub(empty_function_pattern, "\n", source)
    source_fixed = fixup_result(source_without_empty_methods)
    module_node: ast.Module = ast.parse(source_fixed)
    function_definitions = extract_function_defs(module_node)
    return process_function_defs(function_definitions, module_node)


def rewrite_test(fn_def_node: ast.FunctionDef):
    """Reformat the test in fn_def_node.

    So it can be parsed by AstToTestCaseTransformer.

    Args:
        fn_def_node: a function definition to rewrite.

    Returns:
        a rewritten AST node.
    """
    visitor = StmtRewriter()
    visitor.visit(fn_def_node)
    return fn_def_node


class TestClassRewriter(ast.NodeTransformer):
    """A custom AST node transformer for rewriting test classes."""

    def __init__(self):  # noqa: D107
        self.set_up_vars = []
        self.counter = 0
        self.var_mapping = {}

    def visit_ClassDef(self, node: ast.ClassDef):  # noqa:N802
        """Processes a class definition, collecting `setUp` variables.

        Args:
            node (ast.ClassDef): The class definition node.

        Returns:
            ast.ClassDef: The transformed class node.
        """
        for child_node in node.body:
            if isinstance(child_node, ast.FunctionDef) and child_node.name == "setUp":
                self.collect_set_up_vars(child_node)

        for child_node in node.body:
            if isinstance(child_node, ast.FunctionDef) and child_node.name.startswith("test_"):
                self.transform_test_function(child_node)

        return node

    def collect_set_up_vars(self, set_up_node: ast.FunctionDef):
        """Collects variables from `setUp` function, removes `self.` prefix.

        and stores them with unique var_<counter> names.
        """
        for stmt in set_up_node.body:
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
                target = stmt.targets[0]
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    var_name = f"var_{self.counter}"
                    self.var_mapping[target.attr] = var_name
                    self.counter += 1
                    # Create a new assignment with the counter-based variable
                    new_target = ast.Name(id=var_name, ctx=ast.Store())
                    self.set_up_vars.append(ast.Assign(targets=[new_target], value=stmt.value))

    def transform_test_function(self, test_func_node: ast.FunctionDef):
        """Transforms a test function by replacing `self.<variable>`.

        references with `var_<counter>` and removing `self` from
        method calls.

        Adds the transformed `setUp` variables to the start of the
        test function body.

        Args:
            test_func_node (ast.FunctionDef): The test function node
            to transform.
        """
        # Add the transformed `setUp` variables at the start of the test function
        test_func_node.body = self.set_up_vars + [
            self.replace_self_references(stmt) for stmt in test_func_node.body
        ]

    def replace_self_references(self, node):
        """Replaces `self.<variable>` references and removes `self` from method calls.

        Args:
            node (ast.AST): The current AST node to process.

        Returns:
            ast.AST: The modified AST node with `self` references replaced.
        """
        # Handle `self.<variable>` replacement
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            # Check if it's a variable reference or a method call
            return (
                ast.Name(id=self.var_mapping[node.attr], ctx=node.ctx)
                if node.attr in self.var_mapping
                else ast.Name(id=node.attr, ctx=node.ctx)
            )

        # Process any child nodes recursively
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                new_values = [
                    (self.replace_self_references(item) if isinstance(item, ast.AST) else item)
                    for item in value
                ]
                setattr(node, field, new_values)
            elif isinstance(value, ast.AST):
                new_value = self.replace_self_references(value)
                setattr(node, field, new_value)

        return node


def extract_function_defs(module_node: ast.Module) -> list[ast.FunctionDef]:
    """Extract test function definitions with updated `setUp` variables.

    without `self` prefix.
    """
    assert isinstance(module_node, ast.Module)

    rewriter = TestClassRewriter()
    rewriter.visit(module_node)

    # Use a list comprehension to collect all test functions
    return [
        child_node
        for node in module_node.body
        if isinstance(node, ast.ClassDef)
        for child_node in node.body
        if isinstance(child_node, ast.FunctionDef) and child_node.name.startswith("test_")
    ]


def process_function_defs(
    function_defs: list[ast.FunctionDef], module_node: ast.Module
) -> dict[str, str]:
    """Process the extracted FunctionDef nodes and return rewritten tests.

    Args:
        function_defs: a list of function definition nodes.
        module_node: the module node containing the function definitions.

    Returns:
        a dictionary with function names as keys and rewritten tests as values.
    """
    return_tests: dict[str, str] = {}
    for function_def in function_defs:
        test_module = ast.Module(
            body=[rewrite_test(function_def)],
            type_ignores=module_node.type_ignores,
        )
        test_module = ast.fix_missing_locations(test_module)
        try:
            return_tests[function_def.name] = ast.unparse(test_module) + "\n"
        except AttributeError as e:
            logger.info("Got error: %s\nwhen trying to unparse the transformation", e)
    return return_tests


def fixup_result(result):
    """In case we aborted generation early (due to running out of tokens).

    Remove any lingering syntax errors that prevent parsing by the `ast` module.
    There may still be syntax errors when actually running the code.

    Args:
        result: some natural language source code.

    Returns:
        source code that parses with ast.parse.
    """
    try:
        ast.parse(result)
        return result
    except SyntaxError as e:
        line_to_rm = e.lineno
        lines = result.split("\n")
        if line_to_rm is None or line_to_rm >= len(lines):
            return fixup_result("\n".join(lines[:-1]))
        return fixup_result("\n".join(lines[:line_to_rm]))
