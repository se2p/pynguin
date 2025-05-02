#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import ast

import pytest

from pynguin.large_language_model.parsing import rewriter


@pytest.mark.parametrize(
    "llm_output, expected_snippet",
    [
        (
            # Basic setUp + addition
            """
class TestFoo:
    def setUp(self):
        self.x = 1
        self.y = 2

    def test_add(self):
        result = self.x + self.y
        assert result == 3
""",
            [
                "def test_add():",
                "var_0 = 1",
                "var_1 = 2",
                "result = var_0 + var_1",
                "assert result == 3",
            ],
        ),
        (
            # Method call with argument
            """
class TestCall:
    def setUp(self):
        self.data = [1, 2, 3]

    def test_len(self):
        length = len(self.data)
        assert length == 3
""",
            [
                "def test_len():",
                "var_1 = 1",
                "var_2 = 2",
                "var_3 = 3",
                "var_0 = [var_1, var_2, var_3]",
                "length = len(var_0)",
                "assert length == 3",
            ],
        ),
        (
            # isinstance assertion
            """
class TestIsInstance:
    def setUp(self):
        self.value = "hello"

    def test_type(self):
        assert isinstance(self.value, str)
""",
            [
                "def test_type():",
                "var_0 = 'hello'",
                "var_1 = isinstance(var_0, str)",
                "assert var_1",
            ],
        ),
        (
            # Nested attributes
            """
class SomeObject:
    def __init__(self):
        self.value = 5

class TestAttrAccess:
    def setUp(self):
        self.obj = SomeObject()

    def test_attr(self):
        v = self.obj.value
        assert v == 5
""",
            [
                "def test_attr():",
                "var_0 = SomeObject()",
                "v = var_0.value",
                "assert v == 5",
            ],
        ),
    ],
)
def test_rewrite_tests(llm_output, expected_snippet):
    result_dict = rewriter.rewrite_tests(llm_output)
    assert isinstance(result_dict, dict)
    assert any("test_" in fn_name for fn_name in result_dict)

    final_code = "\n".join(result_dict.values())
    for line in expected_snippet:
        assert line in final_code


def test_stmt_rewriter_replace_with_varname():
    """Test the replace_with_varname method of StmtRewriter."""
    visitor = rewriter.StmtRewriter()

    # Test with ast.Name node (line 91)
    name_node = ast.Name(id="x", ctx=ast.Load())
    result = visitor.replace_with_varname(name_node)
    assert result is name_node  # Should return the same node

    # Test with ast.Constant node that's in constant_dict (line 93)
    constant_node = ast.Constant(value=42)
    varname = "var_0"
    visitor.constant_dict[42] = varname
    result = visitor.replace_with_varname(constant_node)
    assert isinstance(result, ast.Name)
    assert result.id == varname

    # Test with node that has bound variables (line 95)
    visitor._bound_variables = {"x"}
    visitor.replace_only_free_subnodes = True
    node_with_bound_var = ast.Name(id="x", ctx=ast.Load())
    result = visitor.replace_with_varname(node_with_bound_var)
    assert result is node_with_bound_var  # Should return the same node


def test_stmt_rewriter_bound_scope_methods():
    """Test the enter_new_bound_scope and exit_bound_scope methods."""
    visitor = rewriter.StmtRewriter()

    # Initial state
    visitor._bound_variables = {"x"}
    visitor.replace_only_free_subnodes = False

    # Test enter_new_bound_scope (lines 122-124)
    visitor.enter_new_bound_scope()
    assert visitor._bound_variables_stack[-1] == {"x"}
    assert visitor._replace_only_free_stack[-1] is False
    assert visitor.replace_only_free_subnodes is True

    # Modify bound variables
    visitor._bound_variables.add("y")

    # Test exit_bound_scope (lines 128-129)
    visitor.exit_bound_scope()
    assert visitor._bound_variables == {"x"}  # Should restore original value
    assert visitor.replace_only_free_subnodes is False  # Should restore original value


def test_visit_only_calls_subnodes():
    """Test the visit_only_calls_subnodes method."""
    visitor = rewriter.StmtRewriter()

    # Create a node with a list field containing items with and without calls
    node_with_call = ast.Call(func=ast.Name(id="func", ctx=ast.Load()), args=[], keywords=[])
    node_without_call = ast.Name(id="var", ctx=ast.Load())

    # Create a parent node with a list field
    parent_node = ast.Module(body=[node_with_call, node_without_call], type_ignores=[])

    # Test visit_only_calls_subnodes (lines 209-211, 216-218)
    result = visitor.visit_only_calls_subnodes(parent_node)

    # Verify the result
    assert isinstance(result, ast.Module)
    assert len(result.body) == 2


def test_visit_unary_op():
    """Test the visit_UnaryOp method."""
    visitor = rewriter.StmtRewriter()

    # Test with constant operand (lines 285-286)
    constant_operand = ast.Constant(value=42)
    unary_op = ast.UnaryOp(op=ast.USub(), operand=constant_operand)
    result = visitor.visit_UnaryOp(unary_op)
    assert result is unary_op  # Should return the same node

    # Test with non-constant operand (line 287)
    name_operand = ast.Name(id="x", ctx=ast.Load())
    unary_op = ast.UnaryOp(op=ast.USub(), operand=name_operand)
    result = visitor.visit_UnaryOp(unary_op)
    assert result is not unary_op  # Should return a transformed node


def test_fixup_result():
    """Test the fixup_result function."""
    # Test with valid code (lines 927-928)
    valid_code = "def test_func():\n    x = 1\n    return x"
    result = rewriter.fixup_result(valid_code)
    assert result == valid_code

    # Test with syntax error (lines 929-934)
    invalid_code = "def test_func():\n    x = 1\n    return x\ndef incomplete_func():"
    result = rewriter.fixup_result(invalid_code)
    # Should remove the incomplete function definition
    assert result == "def test_func():\n    x = 1\n    return x"

    # Test with syntax error at the end (line 933)
    invalid_code_end = "def test_func():\n    x = 1\n    return x\n}"
    result = rewriter.fixup_result(invalid_code_end)
    assert result == "def test_func():\n    x = 1\n    return x"

    # Test with error in process_function_defs (lines 909-910)
    try:
        # Create a situation where ast.unparse would raise an AttributeError
        # by mocking ast.unparse to raise an AttributeError
        # Using exec here is intentional for testing purposes to simulate an error
        original_unparse = ast.unparse
        ast.unparse = lambda _node: exec('raise AttributeError("Test error")')  # noqa: S102

        # Call process_function_defs with a function definition
        fn_def = ast.FunctionDef(
            name="test_func",
            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=[ast.Pass()],
            decorator_list=[],
        )
        result = rewriter.process_function_defs([fn_def], ast.Module(body=[], type_ignores=[]))

        # Should return an empty dict when an error occurs
        assert result == {}
    finally:
        # Restore original unparse function
        ast.unparse = original_unparse


def test_visit_call():
    """Test the visit_Call method."""
    visitor = rewriter.StmtRewriter()

    # Test with normal function call (line 241)
    func = ast.Name(id="func", ctx=ast.Load())
    arg = ast.Starred(value=ast.Name(id="args", ctx=ast.Load()), ctx=ast.Load())
    call = ast.Call(func=func, args=[arg], keywords=[])

    result = visitor.visit_Call(call)
    assert isinstance(result, ast.Call)

    # Test with keyword arguments (lines 247-249)
    kwarg = ast.keyword(arg="kwarg", value=ast.Name(id="value", ctx=ast.Load()))
    call_with_kwargs = ast.Call(func=func, args=[], keywords=[kwarg])

    result = visitor.visit_Call(call_with_kwargs)
    assert isinstance(result, ast.Call)
    assert len(result.keywords) == 1


def test_visit_subscript():
    """Test the visit_Subscript method."""
    visitor = rewriter.StmtRewriter()

    # Test with tuple slice (lines 264-269, 271-272)
    value = ast.Name(id="list", ctx=ast.Load())
    slice_elem1 = ast.Constant(value=1)
    slice_elem2 = ast.Slice(lower=ast.Constant(value=0), upper=ast.Constant(value=5), step=None)
    slice_tuple = ast.Tuple(elts=[slice_elem1, slice_elem2], ctx=ast.Load())
    subscript = ast.Subscript(value=value, slice=slice_tuple, ctx=ast.Load())

    result = visitor.visit_Subscript(subscript)
    assert isinstance(result, ast.Subscript)
    assert isinstance(result.slice, ast.Tuple)

    # Test with slice (lines 273-274)
    slice_obj = ast.Slice(lower=ast.Constant(value=0), upper=ast.Constant(value=5), step=None)
    subscript_with_slice = ast.Subscript(value=value, slice=slice_obj, ctx=ast.Load())

    result = visitor.visit_Subscript(subscript_with_slice)
    assert isinstance(result, ast.Subscript)
    assert isinstance(result.slice, ast.Slice)

    # Test with other slice (lines 276-277, 279, 281)
    other_slice = ast.Constant(value=1)
    subscript_with_other = ast.Subscript(value=value, slice=other_slice, ctx=ast.Load())

    result = visitor.visit_Subscript(subscript_with_other)
    assert isinstance(result, ast.Subscript)


def test_visit_attribute():
    """Test the visit_Attribute method."""
    visitor = rewriter.StmtRewriter()

    # Test with attribute node (lines 308, 312)
    value = ast.Name(id="obj", ctx=ast.Load())
    attr = ast.Attribute(value=value, attr="method", ctx=ast.Load())

    result = visitor.visit_Attribute(attr)
    assert isinstance(result, ast.Attribute)


def test_visit_ann_assign():
    """Test the visit_AnnAssign method."""
    visitor = rewriter.StmtRewriter()

    # Test with annotation assignment (lines 346-348)
    target = ast.Name(id="x", ctx=ast.Store())
    annotation = ast.Name(id="int", ctx=ast.Load())
    value = ast.Constant(value=5)
    ann_assign = ast.AnnAssign(target=target, annotation=annotation, value=value, simple=1)

    result = visitor.visit_AnnAssign(ann_assign)
    # The method should return an Assign node when value is not None
    assert isinstance(result, ast.Assign)
    assert result.targets[0] == target
    # Check that the value has the same Python value, not necessarily the same object
    assert isinstance(result.value, ast.Constant)
    assert result.value.value == value.value


def test_visit_aug_assign():
    """Test the visit_AugAssign method."""
    visitor = rewriter.StmtRewriter()

    # Test with augmented assignment (lines 362-363, 366)
    target = ast.Name(id="x", ctx=ast.Store())
    op = ast.Add()
    value = ast.Constant(value=5)
    aug_assign = ast.AugAssign(target=target, op=op, value=value)

    # Mock the generic_visit method to return a modified node
    original_generic_visit = visitor.generic_visit

    def mock_generic_visit(_node):
        # Create a new AugAssign node with the same fields
        new_target = ast.Name(id=target.id, ctx=ast.Store())
        new_value = ast.Constant(value=value.value)
        return ast.AugAssign(target=new_target, op=op, value=new_value)

    # Replace the generic_visit method with our mock
    visitor.generic_visit = mock_generic_visit

    result = visitor.visit_AugAssign(aug_assign)

    # Restore the original generic_visit method
    visitor.generic_visit = original_generic_visit

    # The method should return an Assign node with a BinOp as the value
    assert isinstance(result, ast.Assign)
    # Check that the target has the same name, not necessarily the same object
    assert isinstance(result.targets[0], ast.Name)
    assert result.targets[0].id == target.id
    assert isinstance(result.value, ast.BinOp)
    # Check that the left operand has the same name, not necessarily the same object
    assert isinstance(result.value.left, ast.Name)
    assert result.value.left.id == target.id
    assert isinstance(result.value.op, ast.Add)
    # Check that the right operand has the same value, not necessarily the same object
    assert isinstance(result.value.right, ast.Constant)
    assert result.value.right.value == value.value


def test_visit_named_expr():
    """Test the visit_NamedExpr method."""
    visitor = rewriter.StmtRewriter()

    # Test with named expression (lines 377-379)
    target = ast.Name(id="x", ctx=ast.Store())
    value = ast.Constant(value=5)
    named_expr = ast.NamedExpr(target=target, value=value)

    # Reset stmts_to_add before calling the method
    visitor.reset_stmts_to_add()

    result = visitor.visit_NamedExpr(named_expr)
    # The method should return the target and add an Assign statement to stmts_to_add
    assert result == target
    assert len(visitor.stmts_to_add) == 1
    assert isinstance(visitor.stmts_to_add[0], ast.Assign)
    # Check that the target has the same name, not necessarily the same object
    assert isinstance(visitor.stmts_to_add[0].targets[0], ast.Name)
    assert visitor.stmts_to_add[0].targets[0].id == target.id
    # Check that the value has the same Python value, not necessarily the same object
    assert isinstance(visitor.stmts_to_add[0].value, ast.Constant)
    assert visitor.stmts_to_add[0].value.value == value.value


def test_visit_lambda():
    """Test the visit_Lambda method."""
    visitor = rewriter.StmtRewriter()

    # Test with lambda (lines 543-554)
    args = ast.arguments(
        posonlyargs=[],
        args=[ast.arg(arg="x", annotation=None)],
        kwonlyargs=[],
        kw_defaults=[],
        defaults=[],
    )
    body = ast.BinOp(
        left=ast.Name(id="x", ctx=ast.Load()), op=ast.Add(), right=ast.Constant(value=1)
    )
    lambda_node = ast.Lambda(args=args, body=body)

    result = visitor.visit_Lambda(lambda_node)
    assert isinstance(result, ast.Lambda)


def test_comprehension_methods():
    """Test the comprehension-related methods."""
    visitor = rewriter.StmtRewriter()

    # Test get_comprehension_bound_vars (line 565)
    target = ast.Name(id="x", ctx=ast.Store())
    iter_expr = ast.Name(id="range", ctx=ast.Load())
    comprehension = ast.comprehension(target=target, iter=iter_expr, ifs=[], is_async=0)

    bound_vars = visitor.get_comprehension_bound_vars(comprehension)
    assert "x" in bound_vars

    # Test _visit_generators_common (lines 576-580)
    generators = [comprehension]
    visitor._visit_generators_common(generators)

    # Test visit_GeneratorExp (lines 593-598)
    elt = ast.Name(id="x", ctx=ast.Load())
    gen_exp = ast.GeneratorExp(elt=elt, generators=generators)

    result = visitor.visit_GeneratorExp(gen_exp)
    assert isinstance(result, ast.GeneratorExp)

    # Test visit_ListComp (lines 609-614)
    list_comp = ast.ListComp(elt=elt, generators=generators)

    result = visitor.visit_ListComp(list_comp)
    assert isinstance(result, ast.ListComp)

    # Test visit_SetComp (lines 625-630)
    set_comp = ast.SetComp(elt=elt, generators=generators)

    result = visitor.visit_SetComp(set_comp)
    assert isinstance(result, ast.SetComp)

    # Test visit_DictComp (lines 641-647)
    key = ast.Name(id="x", ctx=ast.Load())
    value = ast.BinOp(
        left=ast.Name(id="x", ctx=ast.Load()), op=ast.Mult(), right=ast.Constant(value=2)
    )
    dict_comp = ast.DictComp(key=key, value=value, generators=generators)

    result = visitor.visit_DictComp(dict_comp)
    assert isinstance(result, ast.DictComp)


def test_visit_import_methods():
    """Test the import-related visit methods."""
    visitor = rewriter.StmtRewriter()

    # Test visit_Import (line 658)
    import_node = ast.Import(names=[ast.alias(name="os", asname=None)])

    result = visitor.visit_Import(import_node)
    assert result is import_node

    # Test visit_ImportFrom (line 669)
    import_from = ast.ImportFrom(module="os", names=[ast.alias(name="path", asname=None)], level=0)

    result = visitor.visit_ImportFrom(import_from)
    assert result is import_from


def test_visit_async_methods():  # noqa: PLR0914
    """Test the async-related visit methods."""
    visitor = rewriter.StmtRewriter()

    # Test visit_Await (line 680)
    value = ast.Name(id="coro", ctx=ast.Load())
    await_node = ast.Await(value=value)

    result = visitor.visit_Await(await_node)
    assert isinstance(result, ast.Await)

    # Test visit_AsyncFunctionDef (line 691)
    args = ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[])
    async_fn = ast.AsyncFunctionDef(
        name="async_func", args=args, body=[ast.Pass()], decorator_list=[], returns=None
    )

    result = visitor.visit_AsyncFunctionDef(async_fn)
    assert isinstance(result, ast.AsyncFunctionDef)

    # Test visit_AsyncFor (line 702)
    target = ast.Name(id="x", ctx=ast.Store())
    iter_expr = ast.Name(id="async_iter", ctx=ast.Load())
    async_for = ast.AsyncFor(target=target, iter=iter_expr, body=[ast.Pass()], orelse=[])

    result = visitor.visit_AsyncFor(async_for)
    assert isinstance(result, ast.AsyncFor)

    # Test visit_AsyncWith (line 713)
    context_expr = ast.Name(id="async_ctx", ctx=ast.Load())
    optional_vars = ast.Name(id="cm", ctx=ast.Store())
    item = ast.withitem(context_expr=context_expr, optional_vars=optional_vars)
    async_with = ast.AsyncWith(items=[item], body=[ast.Pass()])

    result = visitor.visit_AsyncWith(async_with)
    assert isinstance(result, ast.AsyncWith)

    # Test visit_Match (line 724)
    subject = ast.Name(id="value", ctx=ast.Load())
    pattern = ast.MatchValue(value=ast.Constant(value=1))
    case = ast.match_case(pattern=pattern, guard=None, body=[ast.Pass()])
    match = ast.Match(subject=subject, cases=[case])

    result = visitor.visit_Match(match)
    assert isinstance(result, ast.Match)
