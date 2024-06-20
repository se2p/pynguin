#  This file is part of CodaMOSA
#
#  SPDX-FileCopyrightText: Microsoft
#
#  SPDX-License-Identifier: MIT
#
import ast
import logging
import re

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from pynguin import configuration as config

logger = logging.getLogger()


def extract_python_code_from_llm_output(llm_output: str) -> str:
    """Extracts Python code blocks from the LLM output.

    Args:
        llm_output: The output from the LLM containing Python code.

    Returns:
        The extracted Python code.

    Raises:
        ValueError: If no Python code block is found in the LLM output.
    """
    # code_blocks = re.findall(r"```python([\s\S]+?)```", llm_output)
    # if not code_blocks:
    #     raise ValueError("No Python code block found in the LLM output.")
    # return "\n".join(code_blocks)
    return llm_output


def extract_test_cases_from_llm_output(llm_output):
    python_code = extract_python_code_from_llm_output(llm_output)
    generated_tests: Dict[str, str] = rewrite_tests(python_code)
    str_test_cases = "\n\n".join(generated_tests.values())
    return str_test_cases


def is_expr_or_stmt(node: ast.AST):
    """
    Whether node is an expression or statement, i.e. whether it potentially has useful
    children to recurse into. This excludes constants like ast.Load, ast.Store.

    Args:
        node: an ast Node

    Returns:
        Whether node is an expression or statement
    """
    return isinstance(node, ast.expr) or isinstance(node, ast.stmt)


def has_call(node: ast.AST):
    """
    Returns true if node if it has descendant nodes that are calls.

    Args:
        node: an ast Node

    Returns:
        Whether node has a call in one of its descendant
    """

    class CallFinder(ast.NodeVisitor):
        def __init__(self):
            super().__init__()
            self.has_call = False

        def visit_Call(self, call: ast.Call):
            self.has_call = True

    finder = CallFinder()
    finder.visit(node)
    return finder.has_call


def key_in_dict(value, d):
    """Turns out that `True in {1: 2}` returns True! Let's get rid of that...

    Args:
        value: a key
        d: a dictionary

    Returns:
        true is `value` is actually in the keys of `d`
    """
    if isinstance(value, bool):
        return any([k is value for k in d.keys()])
    else:
        return value in d


def has_bound_variables(node: ast.AST, bound_variables: Set[str]) -> bool:
    """Returns true if node has references to the variables in `bound_variables`.

    Args:
        node: the node to visit
        bound_variables: the set of variables which are bound

    Returns:
        true if node has references to the variables in `bound_variables`.
    """

    class BoundVariableVisitor(ast.NodeVisitor):
        """Helper class that identifies if any names are in `bound_variables`"""

        def __init__(self):
            self.has_bound_variable = False

        def visit_Name(self, node: ast.Name):
            if node.id in bound_variables:
                self.has_bound_variable = True

    bound_variable_visitor = BoundVariableVisitor()
    bound_variable_visitor.visit(node)
    return bound_variable_visitor.has_bound_variable


class StmtRewriter(ast.NodeTransformer):
    """
    Rewrites a statement as much as possible:
    - If it can be rewritten as an assignment statement, write it as an assignment
    - Each child expression of the expression on the statement's RHS is rewritten
      so it is a variable reference, and a variable assignment is added defining
      that variable to the correct expression

    Exceptions:
        - Currently don't recurse into function definitions or lambdas.
        - Call expressions are allowed to have a single-level attribute
          expression as the function being called.
    """

    def __init__(self):
        self.stmts_to_add: List[ast.stmt] = []
        # We don't track this in e.g. function calls because there
        # are no scoping issues in extracting subexpressions there
        self._bound_variables: Set[str] = set()
        self.replace_only_free_subnodes = False

        self._bound_variables_stack: List[Set[str]] = []
        self._replace_only_free_stack: List[bool] = []

        # State that matters for block-level scoping
        self.used_varnames: Set[str] = set()
        self.var_counter = 0
        self.constant_dict = {}
        self.used_varnames_stack: List[Set[str]] = []
        self.var_counter_stack: List[int] = []
        self.constant_dict_stack: List[Dict[Any, ast.Name]] = []
        super().__init__()

    ## Helpers ##

    def reset_stmts_to_add(self):
        """
        Call after visit to avoid adding redundant statements.
        """
        self.stmts_to_add = []

    def fresh_varname(self):
        """
        Get a fresh variable name.

        Returns:
            a new variable name
        """
        new_varname = "var_" + str(self.var_counter)
        self.var_counter += 1
        while new_varname in self.used_varnames:
            # In case var_X is already defined in this test
            new_varname = "var_" + str(self.var_counter)
            self.var_counter += 1
        self.used_varnames.add(new_varname)
        return new_varname

    def replace_with_varname(self, node):
        """
        Returns a ast.Name node to replace `node` with, or no-op if `node` is already
        a name.

        Args:
            node: an ast Node

        Returns:
            an ast.Name node to replace `node` with
        """
        if isinstance(node, ast.Name):
            return node
        if isinstance(node, ast.Constant) and key_in_dict(
            node.value, self.constant_dict
        ):
            varname = self.constant_dict[node.value]
        elif self.replace_only_free_subnodes and has_bound_variables(
            node, self._bound_variables
        ):
            return node
        else:
            varname = self.fresh_varname()
            if isinstance(node, ast.Constant):
                self.constant_dict[node.value] = varname
            assign_decl = ast.Assign(
                targets=[ast.Name(varname, ctx=ast.Store())], value=node
            )
            self.stmts_to_add.append(assign_decl)

        name_node = ast.Name(varname, ctx=ast.Load())
        return name_node

    def enter_new_block_scope(self):
        """Call when entering a new variable name scope"""
        self.used_varnames_stack.append(self.used_varnames)
        self.var_counter_stack.append(self.var_counter)
        self.constant_dict_stack.append(self.constant_dict)
        self.used_varnames = set()
        self.var_counter = 0
        self.constant_dict = {}

    def exit_block_scope(self):
        """Call when exiting a new variable name scope"""
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
        """
        Get all the assignment statements that were created while visiting.

        Returns:
            the statements that were added during the visit
        """
        return self.stmts_to_add

    def visit_block_helper(self, block: List[ast.stmt]):
        """Helper to visit a list of statements, as in a function body or if body.

        Args:
            block: the body to visit.

        Returns:
            a list of ast statements
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
        """
        Returns an ast node of the same type as `node`, but with any ast.AST
        nodes replaced with ast.Name nodes. The core difference with the
        standard generic_visitor is that nodes are replaced with varnames
        after visitng.

        Args:
            node: the node to visit

        Returns:
            the transformed node
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
        """
        Same as above but only visits subnodes which contain function calls.

        Args:
            node: the node to visit

        Returns:
            the transformed node
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

    ## Cases with special handling ##

    def visit_Call(self, call: ast.Call):
        """
        When visiting a call expression, allow the callee to be an ast.Attribute of one
        level, i.e. q.foo()

        Args:
            call: the call node to visit

        Returns:
            the transformed node
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

    def visit_Subscript(self, subscript: ast.Subscript):
        """Subscripts can be both element accesses in a list/dict, or a
        parameterization. Don't separate the LHS into its own variable
        if it's an attribute reference.

        Args:
            subscript: the subscript node to visit

        Returns:
            the transformed node
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

    def visit_UnaryOp(self, node):
        if isinstance(node.operand, ast.Constant):
            return node
        else:
            return self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
        """When visiting attribute nodes, keep repeated dereferences if they are
        just attribute/field accesses, but separate calls into their own functions.

        This may get us into trouble with separating out field/property accesses but
        it saves us from stripping out modules into variables.

        E.g.
            typed_ast._ast3.parse(var_0) should not be transformed
            ast_0.fix_stuff().foo() should have ast_0.fix_stuff() put into a new var

        Args:
            node: the attribute node to visit.

        Returns:
            the transformed node
        """
        value_visited = self.visit(node.value)
        if isinstance(node.value, ast.Attribute):
            node.value = value_visited
        else:
            node.value = self.replace_with_varname(value_visited)
        return node

    def visit_Assign(self, assign: ast.Assign):
        """
        When visiting an assignment statement, the right hand side expression does not need
        to become a variable reference.

        Args:
            assign: the assign node to visit

        Returns:
            the transformed node
        """
        for target in assign.targets:
            if isinstance(target, ast.Name):
                self.used_varnames.add(target.id)
        new_rhs = self.visit(assign.value)
        return ast.Assign(
            targets=assign.targets, value=new_rhs, type_comment=assign.type_comment
        )

    def visit_AnnAssign(self, node: ast.AnnAssign):
        """Convert annotated assigns as well to the correct format, but stripping
        their type annotations

        Args:
            node: the node to visit

        Returns:
            the transformed node
        """
        if node.value is not None:
            return self.visit(ast.Assign(targets=[node.target], value=node.value))
        else:
            return None

    def visit_AugAssign(self, node):
        """Convert augmented assigns to regular assigns. Right now
        `statement_deserializer` wouldn't support the operations on the RHS anyway,
        but worth a try.

        Args:
            node: the node to visit

        Returns:
            the transformed node

        """
        new_aug_assign = self.generic_visit(node)
        rhs_binop = ast.BinOp(
            left=new_aug_assign.target, op=new_aug_assign.op, right=new_aug_assign.value
        )
        return ast.Assign(targets=[new_aug_assign.target], value=rhs_binop)

    def visit_NamedExpr(self, node: ast.NamedExpr):
        """Transform walrus expressions to regular assigns + uses (x := 3)

        Args:
            node: the node to visit

        Returns:
            the transformed node

        """
        rhs = self.visit(node.value)
        self.stmts_to_add.append(ast.Assign(targets=[node.target], value=rhs))
        return node.target

    def visit_Expr(self, expr: ast.Expr):
        """
        A standalone ast.Expr node is an expression as statement. The value field
        stores the actual expr object. Again, we don't want to replace that whole
        expression with a variable reference, instead create an assignment statement
        to contain the expr

        Args:
            expr: the node to visit

        Returns:
            the transformed node
        """
        if isinstance(expr.value, ast.NamedExpr):
            rhs = self.visit(expr.value.value)
            return ast.Assign(targets=[expr.value.target], value=rhs)
        # Don't mess with awaits/yields
        if type(expr.value) in (ast.Await, ast.Yield, ast.YieldFrom):
            return expr
        rhs = self.visit(expr.value)
        return ast.Assign(
            targets=[ast.Name(id=self.fresh_varname(), ctx=ast.Store)], value=rhs
        )

    def visit_Assert(self, assert_node: ast.Assert):
        """
        We want the test's upper level comparators to remain, but extract the
        sub-expressions into variables when they contain calls.

        Args:
            assert_node: the node to visit

        Returns:
            the transformed node
        """
        if isinstance(assert_node.test, ast.Call):
            return self.generic_visit(assert_node)
        else:
            new_test = self.visit_only_calls_subnodes(assert_node.test)
        return ast.Assert(new_test)

    def visit_FunctionDef(self, fn_def_node: ast.FunctionDef):
        """Reformats the test in fn_def_node so it can be parsed by
        initial population seeding module.

        Args:
            fn_def_node: the node to visit

        Returns:
            the transformed node
        """
        if not fn_def_node.name.startswith("test_"):
            return fn_def_node

        # Visit the main body
        new_body = self.visit_block_helper(fn_def_node.body)
        fn_def_node.body = new_body
        ast.fix_missing_locations(fn_def_node)

        return fn_def_node

    def visit_ClassDef(self, node: ast.ClassDef):
        if any(
            [
                isinstance(stmt, ast.FunctionDef) and stmt.name.startswith("test_")
                for stmt in node.body
            ]
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

    # These could be simplified into a single visitor, but for the
    # fact that we don't want to visit the tests/iterexpressions.
    # That single visitor would just call visit_block_helper on any blocks
    # (list of only statements.
    #
    # But we don't want to turn, e.g. the test for while into a
    # subexpression.

    def visit_For(self, node):
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        return node

    def visit_While(self, node: ast.While):
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        return node

    def visit_If(self, node):
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        return node

    def visit_With(self, node):
        node.body = self.visit_block_helper(node.body)
        return node

    def visit_Try(self, node: ast.Try):
        node.body = self.visit_block_helper(node.body)
        node.orelse = self.visit_block_helper(node.orelse)
        node.finalbody = self.visit_block_helper(node.finalbody)
        return node

    def visit_Lambda(self, node: ast.Lambda):
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

    def get_comprehension_bound_vars(self, node: ast.comprehension) -> List[str]:
        return [elem.id for elem in ast.walk(node.target) if isinstance(elem, ast.Name)]

    def _visit_generators_common(self, generators: List[ast.comprehension]):
        new_generators = []
        for comp in generators:
            self._bound_variables.update(self.get_comprehension_bound_vars(comp))
            new_generators.append(self.visit(comp))
        return new_generators

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> ast.GeneratorExp:
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.GeneratorExp(elt=new_elt, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    def visit_ListComp(self, node: ast.ListComp) -> ast.ListComp:
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.ListComp(elt=new_elt, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    def visit_SetComp(self, node: ast.SetComp) -> ast.SetComp:
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_elt = self.visit(node.elt)
        ret_val = ast.SetComp(elt=new_elt, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    def visit_DictComp(self, node: ast.DictComp) -> ast.DictComp:
        self.enter_new_bound_scope()
        new_generators = self._visit_generators_common(node.generators)
        new_key = self.visit(node.key)
        new_value = self.visit(node.value)
        ret_val = ast.DictComp(key=new_key, value=new_value, generators=new_generators)
        self.exit_bound_scope()
        return ret_val

    ## Things we want to leave unmodified ##

    def visit_Import(self, node):
        return node

    def visit_ImportFrom(self, node):
        return node

    def visit_Await(self, node):
        return node

    def visit_AsyncFunctionDef(self, node):
        return node

    def visit_AsyncFor(self, node):
        return node

    def visit_AsyncWith(self, node):
        return node

    def visit_Match(self, node):
        return node


def rewrite_test(fn_def_node: ast.FunctionDef):
    """
    Reformats the test in fn_def_node so it can be parsed by AstToTestCaseTransformer

    Args:
        fn_def_node: a function definition to rewrite

    Returns:
        a rewritten AST node
    """
    visitor = StmtRewriter()
    visitor.visit(fn_def_node)
    return fn_def_node


def fixup_result(result):
    """
    In case we aborted generation early (due to running out of tokens), remove
    any lingering syntax errors that prevent parsing by the `ast` module.
    (There may still be syntax errors when actually running the code)

    Args:
        result: some natural language source code

    Returns:
        source code that parses with ast.pasrse
    """
    try:
        ast.parse(result)
        return result
    except SyntaxError as e:
        line_to_rm = e.lineno
        lines = result.split("\n")
        if line_to_rm is None or line_to_rm >= len(lines):
            return fixup_result("\n".join(lines[:-1]))
        else:
            return fixup_result("\n".join(lines[:line_to_rm]))


def extract_function_defs(source: str) -> List[ast.FunctionDef]:
    """Extract all FunctionDef nodes from the source code."""
    source = fixup_result(source)
    module_node: ast.Module = ast.parse(source)
    assert isinstance(module_node, ast.Module)

    function_defs = []
    for node in module_node.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            function_defs.append(node)
        elif isinstance(node, ast.ClassDef):
            for child_node in node.body:
                if isinstance(child_node, ast.FunctionDef) and child_node.name.startswith("test_"):
                    function_defs.append(child_node)
    return function_defs


def process_function_defs(function_defs: List[ast.FunctionDef], module_node: ast.Module) -> Dict[str, str]:
    """Process the extracted FunctionDef nodes and return rewritten tests."""
    return_tests: Dict[str, str] = {}
    for function_def in function_defs:
        test_module = ast.Module(
            body=[rewrite_test(function_def)],
            type_ignores=module_node.type_ignores,
        )
        test_module = ast.fix_missing_locations(test_module)
        try:
            return_tests[function_def.name] = ast.unparse(test_module) + "\n"
        except AttributeError as e:
            logger.info(
                "Got error: %s\nwhen trying to unparse the transformation"
                " of %s from:\n%s",
                e,
                function_def.name,
                ast.unparse(function_def),
            )
    return return_tests


def rewrite_tests(source: str) -> Dict[str, str]:
    """Rewrite the tests in `source` so that they can be parsed by AstToTestCaseTransformer."""
    module_node: ast.Module = ast.parse(source)
    function_defs = extract_function_defs(source)
    return process_function_defs(function_defs, module_node)


def fixup_imports(test_case_str: str, node: Optional[ast.Module] = None):
    """
    Remove qualified imports for the module under test.

    Args:
        test_case_str: the test case as string to fixup
        node: the ast.Module node corresponding to test_case_str/its parent

    Returns:
        test_case_str with the calls to functions in the test module de-qualified
    """
    if node is None:
        node = ast.parse(test_case_str)
    imports: List[ast.Import] = [
        elem for elem in node.body if isinstance(elem, ast.Import)
    ]
    quals_to_replace = {}
    for import_ in imports:
        for name in import_.names:
            if name.asname is None:
                continue
            if config.configuration.module_name in name.name:
                quals_to_replace[name.asname + "."] = ""
            else:
                pass
                # quals_to_replace[name.asname + "."] = name.name + "."
    test_case_str = "\n".join(
        [
            line
            for line in test_case_str.split("\n")
            if f"import {config.configuration.module_name}" not in line
        ]
    )
    for alias_to_replace, replace_name in quals_to_replace.items():
        test_case_str = test_case_str.replace(alias_to_replace, replace_name)
    return test_case_str
