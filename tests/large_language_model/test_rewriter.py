#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import ast

import pytest

import pynguin.configuration as config
from pynguin.analyses.module import ModuleTestCluster
from pynguin.large_language_model.parsing import rewriter
from pynguin.large_language_model.parsing.deserializer import deserialize_code_to_testcases


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
                "x = 1",
                "y = 2",
                "result = x + y",
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
                "data = [1, 2, 3]",
                "length = len(data)",
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
                "value = 'hello'",
                "assert isinstance(value, str)",
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
                "obj = SomeObject()",
                "v = obj.value",
                "assert v == 5",
            ],
        ),
        (
            # pytest xUnit-style setup_method fixture (issue #303)
            """
class TestDiffMatchPatch:
    def setup_method(self):
        self.dmp = diff_match_patch()

    def test_diff(self):
        diffs = self.dmp.diff_main("Hello", "Helo")
        assert diffs is not None
""",
            [
                "def test_diff():",
                "dmp = diff_match_patch()",
                "diffs = dmp.diff_main('Hello', 'Helo')",
                "assert diffs is not None",
            ],
        ),
        (
            # pytest nose-style setup fixture
            """
class TestSetup:
    def setup(self):
        self.data = [1, 2, 3]

    def test_len(self):
        assert len(self.data) == 3
""",
            [
                "def test_len():",
                "data = [1, 2, 3]",
                "assert len(data) == 3",
            ],
        ),
        (
            # pytest setup_class fixture (uses cls)
            """
class TestSetupClass:
    @classmethod
    def setup_class(cls):
        cls.obj = SomeObject()

    def test_attr(self):
        assert self.obj is not None
""",
            [
                "def test_attr():",
                "obj = SomeObject()",
                "assert obj is not None",
            ],
        ),
    ],
)
def test_rewrite_tests(llm_output, expected_snippet):
    result = rewriter.rewrite_tests(llm_output)
    assert isinstance(result.functions, dict)
    assert any("test_" in fn_name for fn_name in result.functions)

    final_code = "\n".join(result.functions.values())
    for line in expected_snippet:
        assert line in final_code


def test_rewrite_tests_preserves_self_in_nested_class():
    """A local class defined inside a test method keeps its own ``self.`` attributes.

    ``self`` inside the nested class's methods refers to the nested instance, not the
    unittest test-class instance, so stripping it would corrupt the class and make the
    emitted test raise ``UnboundLocalError``/``AttributeError`` at runtime.
    """
    llm_output = """
class TestCounter:
    def test_bump(self):
        class Counter:
            def __init__(self):
                self.n = 0
            def bump(self):
                self.n += 1
                return self.n
        c = Counter()
        r = c.bump()
        assert r == 1
"""
    final_code = "\n".join(rewriter.rewrite_tests(llm_output).functions.values())
    # The nested class must keep its instance-attribute access untouched.
    assert "self.n = 0" in final_code
    assert "self.n += 1" in final_code
    assert "return self.n" in final_code
    # The rewritten function must actually run without error.
    namespace: dict = {}
    exec(final_code, namespace)  # noqa: S102
    next(fn for name, fn in namespace.items() if name.startswith("test_"))()


def test_rewrite_tests_strips_self_at_test_method_scope():
    """The test method's own ``self.`` (unittest instance) is still stripped."""
    llm_output = """
class TestFoo:
    def setUp(self):
        self.value = 5

    def test_use(self):
        result = self.value + 1
        assert result == 6
"""
    final_code = "\n".join(rewriter.rewrite_tests(llm_output).functions.values())
    assert "result = value + 1" in final_code
    assert "self.value" not in final_code


def test_rewrite_tests_preserves_self_in_nested_function():
    """``self`` used inside a nested ``def`` is a parameter of that function, not the test."""
    llm_output = """
class TestFoo:
    def test_helper(self):
        def describe(self):
            return self.name
        assert describe is not None
"""
    final_code = "\n".join(rewriter.rewrite_tests(llm_output).functions.values())
    assert "return self.name" in final_code


def test_stmt_rewriter_replace_with_varname():
    """Test the replace_with_varname method of StmtRewriter."""
    visitor = rewriter.StmtRewriter()

    name_node = ast.Name(id="x", ctx=ast.Load())
    result = visitor.replace_with_varname(name_node)
    assert result is name_node

    constant_node = ast.Constant(value=42)
    result = visitor.replace_with_varname(constant_node)
    assert result is constant_node


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

    result = visitor.visit_only_calls_subnodes(parent_node)

    assert isinstance(result, ast.Module)
    assert len(result.body) == 2


def test_visit_unary_op():
    """Test the visit_UnaryOp method."""
    visitor = rewriter.StmtRewriter()

    constant_operand = ast.Constant(value=42)
    unary_op = ast.UnaryOp(op=ast.USub(), operand=constant_operand)
    result = visitor.visit_UnaryOp(unary_op)
    assert isinstance(result, ast.UnaryOp)


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
        result = rewriter.process_function_defs(
            [("test_func", fn_def)], ast.Module(body=[], type_ignores=[])
        )

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


def test_rewrite_tests_surfaces_top_level_imports():
    source = (
        "from unittest.mock import patch\n"
        "import tempfile\n"
        "import os\n"
        "\n"
        "def test_foo():\n"
        "    import json\n"  # not top-level -> ignored
        "    x = 1\n"
    )
    assert rewriter.rewrite_tests(source).module_imports == [
        "from unittest.mock import patch",
        "import tempfile",
        "import os",
    ]


def test_rewrite_tests_surfaces_no_imports_when_there_are_none():
    source = "x = 1\n\ndef test_foo():\n    y = 2\n"
    assert rewriter.rewrite_tests(source).module_imports == []


def test_rewrite_tests_surfaces_imports_despite_trailing_syntax_error():
    source = (
        "import tempfile\n"
        "\n"
        "def test_foo():\n"
        "    x = 1\n"
        "def test_broken(:\n"  # truncated / broken tail, as with early LLM abort
    )
    assert "import tempfile" in rewriter.rewrite_tests(source).module_imports


def test_rewrite_tests_keeps_same_named_methods_in_different_classes():
    code = """
class TestA:
    def test_eq(self):
        assert 1 == 1
class TestB:
    def test_eq(self):
        assert 2 == 2
"""
    result = rewriter.rewrite_tests(code)
    assert list(result.functions) == ["TestA.test_eq", "TestB.test_eq"]
    assert "1 == 1" in result.functions["TestA.test_eq"]
    assert "2 == 2" in result.functions["TestB.test_eq"]


def test_rewrite_tests_keeps_duplicate_top_level_functions():
    code = """
def test_eq():
    assert 1 == 1
def test_eq():
    assert 2 == 2
"""
    result = rewriter.rewrite_tests(code)
    assert list(result.functions) == ["test_eq", "test_eq_2"]


def test_rewrite_nested_class_to_dynamic_type_descriptor_pattern():
    code = """
def test_0():
    def my_prop(cls):
        return 42

    class MyClass:
        my_prop = my_prop

    assert MyClass.my_prop == 42
"""
    result = rewriter.rewrite_tests(code)
    assert "test_0" in result.functions
    func_code = result.functions["test_0"]
    assert "MyClass = type('MyClass', (), {'my_prop': my_prop})" in func_code
    assert "class MyClass" not in func_code


def test_rewrite_nested_class_with_bases_and_pass():
    code = """
def test_1():
    class Dummy(Base):
        \"\"\"Docstring\"\"\"
        pass
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_1"]
    assert "Dummy = type('Dummy', (Base,), {})" in func_code
    assert "class Dummy" not in func_code


def test_rewrite_nested_class_with_multiple_attributes_and_annotations():
    code = """
def test_2():
    class Holder:
        a: int = 1
        b = "val"
        c: str
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_2"]
    assert "Holder = type('Holder', (), {'a': 1, 'b': 'val'})" in func_code
    assert "class Holder" not in func_code


def test_rewrite_nested_class_with_methods():
    code = """
def test_3():
    class Calculator:
        def add(self, x, y):
            return x + y
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_3"]
    assert "def _Calculator_add(self, x, y):" in func_code
    assert "Calculator = type('Calculator', (), {'add': _Calculator_add})" in func_code
    assert "class Calculator" not in func_code


def test_rewrite_nested_class_with_decorated_methods():
    code = """
def test_4():
    class PropHolder:
        @property
        def prop(self):
            return 100
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_4"]
    assert "@property" in func_code
    assert "def _PropHolder_prop(self):" in func_code
    assert "PropHolder = type('PropHolder', (), {'prop': _PropHolder_prop})" in func_code


def test_preserve_nested_class_with_zero_arg_super():
    code = """
def test_5():
    class Child(Parent):
        def method(self):
            return super().method()
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_5"]
    assert "class Child(Parent):" in func_code
    assert "super().method()" in func_code


def test_preserve_nested_class_with_class_decorator():
    code = """
def test_6():
    @dataclass
    class DataHolder:
        x: int
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_6"]
    assert "@dataclass" in func_code
    assert "class DataHolder:" in func_code


def test_preserve_nested_class_with_keywords():
    code = """
def test_7():
    class MetaHolder(metaclass=ABCMeta):
        pass
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_7"]
    assert "class MetaHolder(metaclass=ABCMeta):" in func_code


def test_preserve_nested_class_with_unsupported_statement():
    code = """
def test_8():
    class SideEffectHolder:
        side_effect()
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_8"]
    assert "class SideEffectHolder:" in func_code


def test_integration_nested_class_deserialization():
    config.configuration.module_name = "math"
    raw_test = """
def test_property():
    def my_prop(cls):
        return 42

    class MyClass:
        my_prop = my_prop

    res = MyClass.my_prop
    assert res == 42
"""
    rewritten = rewriter.rewrite_tests(raw_test)
    rewritten_code = rewritten.functions["test_property"]
    res = deserialize_code_to_testcases(rewritten_code, ModuleTestCluster(0))
    assert res.status.name == "OK"
    assert len(res.test_cases) == 1
    tc = res.test_cases[0]
    assert tc.size() >= 3


def test_preserve_nested_class_with_non_name_assign_target():
    code = """
def test_9():
    class ComplexTarget:
        a.b = 1
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_9"]
    assert "class ComplexTarget:" in func_code


def test_preserve_nested_class_with_non_name_annassign_target():
    code = """
def test_10():
    class ComplexAnnTarget:
        a.b: int = 1
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_10"]
    assert "class ComplexAnnTarget:" in func_code


def test_rewrite_nested_class_method_name_collision_resolves():
    code = """
def test_11():
    _Calculator_add = 1
    class Calculator:
        def add(self):
            return 2
"""
    result = rewriter.rewrite_tests(code)
    func_code = result.functions["test_11"]
    assert "class Calculator" not in func_code
    assert "Calculator = type('Calculator', (), {'add': var_0})" in func_code


def test_fixup_result_salvages_mid_file_syntax_error(caplog):
    """Test that a mid-file syntax error drops only that test and keeps subsequent tests."""
    code = """def test_a():
    assert 1

def test_b():
    f(1='a')

def test_c():
    assert 2
"""
    with caplog.at_level("INFO"):
        res = rewriter.rewrite_tests(code)

    assert "test_a" in res.functions
    assert "test_b" not in res.functions
    assert "test_c" in res.functions
    assert any(
        "Dropped 1 test(s) due to syntax error" in record.message for record in caplog.records
    )


def test_fixup_result_mid_file_decorated_function():
    """Test that decorators on a malformed mid-file test are dropped together with it."""
    code = """import pytest

def test_first():
    assert 1

@pytest.mark.skip(reason="wip")
@pytest.mark.parametrize("x", [1, 2])
def test_malformed():
    f(1='a')

def test_subsequent():
    assert 3
"""
    res = rewriter.rewrite_tests(code)
    assert "test_first" in res.functions
    assert "test_malformed" not in res.functions
    assert "test_subsequent" in res.functions


def test_fixup_result_mid_file_class():
    """Test that a malformed class in the middle of a file is dropped without losing other tests."""
    code = """def test_before():
    assert 1

class TestMalformed:
    def test_bad(self):
        f(1='a')

def test_after():
    assert 2
"""
    res = rewriter.rewrite_tests(code)
    assert "test_before" in res.functions
    assert not any("TestMalformed" in name for name in res.functions)
    assert "test_after" in res.functions


@pytest.mark.filterwarnings("ignore:invalid decimal literal:DeprecationWarning")
def test_fixup_result_mid_file_invalid_statement():
    """Test that an invalid top-level statement is dropped while keeping surrounding tests."""
    code = """def test_first():
    assert 1

g.1invalid = 1

def test_second():
    assert 2
"""
    res = rewriter.rewrite_tests(code)
    assert "test_first" in res.functions
    assert "test_second" in res.functions


def test_fixup_result_keyword_arg_syntax_error():
    """Test bidict-style invalid keyword argument syntax drops only the enclosing test."""
    code = """def test_valid_pre():
    assert True

def test_invalid_keyword():
    bi = ConcreteBidict(1='a', 2='b')
    assert len(bi) == 2

def test_valid_post():
    assert False is False
"""
    res = rewriter.rewrite_tests(code)
    assert "test_valid_pre" in res.functions
    assert "test_invalid_keyword" not in res.functions
    assert "test_valid_post" in res.functions


def test_fixup_result_multiline_string_with_col0_content():
    """Test that multiline strings containing lines at column 0 are not split into chunks."""
    code = '''def test_with_multiline():
    s = """line1
line2
line3"""
    assert s

def test_bad():
    f(1='a')

def test_good():
    assert 42
'''
    res = rewriter.rewrite_tests(code)
    assert "test_with_multiline" in res.functions
    assert "test_bad" not in res.functions
    assert "test_good" in res.functions


def test_fixup_result_multiple_mid_file_errors():
    """Test that multiple malformed tests in different parts of a file are dropped."""
    code = """def test_1():
    assert 1

def test_bad_1():
    f(1='a')

def test_2():
    assert 2

def test_bad_2():
    g(2='b')

def test_3():
    assert 3
"""
    res = rewriter.rewrite_tests(code)
    assert "test_1" in res.functions
    assert "test_bad_1" not in res.functions
    assert "test_2" in res.functions
    assert "test_bad_2" not in res.functions
    assert "test_3" in res.functions
