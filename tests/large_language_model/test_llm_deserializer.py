#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the LLM Deserializer."""

import ast
import inspect
import math
import textwrap

from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import create_autospec
from unittest.mock import patch

import pytest

import pynguin.testcase.statement as stmt

from pynguin.analyses.typesystem import AnyType
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import TypeInfo
from pynguin.assertion.assertion import FloatAssertion
from pynguin.assertion.assertion import ObjectAssertion
from pynguin.large_language_model.parsing.deserializer import AstToTestCaseTransformer
from pynguin.large_language_model.parsing.deserializer import StatementDeserializer
from pynguin.large_language_model.parsing.deserializer import (
    deserialize_code_to_testcases,
)
from pynguin.testcase import defaulttestcase as dtc
from pynguin.testcase import variablereference as vr
from pynguin.testcase.variablereference import FieldReference
from pynguin.testcase.variablereference import VariableReference
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod


@pytest.fixture
def test_cluster():
    mock_cluster = MagicMock()

    mock_type_info = MagicMock()

    mock_type_system = MagicMock()
    mock_type_system.to_type_info.return_value = mock_type_info

    mock_cluster.type_system = mock_type_system
    mock_cluster.accessible_objects_under_test = []

    return mock_cluster


@pytest.fixture
def deserializer(test_cluster):
    return StatementDeserializer(test_cluster)


def test_assign_constant(deserializer):
    assign_node = ast.parse("x = 42").body[0]  # ast.Assign
    assert deserializer.add_assign_stmt(assign_node)
    testcase = deserializer.get_test_case()
    assert isinstance(testcase, dtc.DefaultTestCase)
    assert len(testcase.statements) == 1


def test_unary_op_assign(deserializer):
    assign_node = ast.parse("y = -10").body[0]
    assert deserializer.add_assign_stmt(assign_node)
    assert isinstance(deserializer.get_test_case(), dtc.DefaultTestCase)


def test_collection_assign_list(deserializer):
    assign_node = ast.parse("mylist = [1, 2, 3]").body[0]
    assert deserializer.add_assign_stmt(assign_node)
    assert isinstance(deserializer.get_test_case(), dtc.DefaultTestCase)


def test_deserialize_code_to_testcases_success(test_cluster):
    code = """
def test_addition():
    x = 1
    y = 2
    s = x + y
"""
    result = deserialize_code_to_testcases(code, test_cluster)
    assert result is not None
    testcases, total, parsed, _ = result
    assert isinstance(testcases, list)
    assert total == 3
    assert parsed == 3


def test_ast_transformer_partial_parse(test_cluster):
    code = """
def test_incomplete():
    var_0 = 2
    x = some_unknown_func()
"""
    transformer = AstToTestCaseTransformer(test_cluster, create_assertions=True)
    transformer.visit(ast.parse(code))
    assert len(transformer.testcases) == 1
    assert transformer.total_parsed_statements < transformer.total_statements


def test_deserializer_handles_invalid_code(test_cluster):
    invalid_code = "def test_broken(:"
    result = deserialize_code_to_testcases(invalid_code, test_cluster)
    assert result is None


def test_visit_assert_with_or_logic(test_cluster):
    code = """
def test_or_assert():
    assert x == 1 or y == 2
"""
    tree = ast.parse(code)
    func_def = tree.body[0]
    assert_node = func_def.body[0]  # ast.Assert

    transformer = AstToTestCaseTransformer(test_cluster, create_assertions=True)
    transformer._deserializer.add_assert_stmt = MagicMock()
    transformer.visit_Assert(assert_node)
    assert transformer._deserializer.add_assert_stmt.call_count == 2


def test_try_generating_specific_function_all_paths(deserializer):
    def call_with_func(func_id, args=None):
        return ast.Call(func=ast.Name(id=func_id, ctx=ast.Load()), args=args or [], keywords=[])

    # --- Case 1: func_id in builtins_dict ---
    with patch.object(
        deserializer, "create_ast_assign_stmt", return_value="assign_stmt"
    ) as ast_assign_mock:
        call = call_with_func("print")  # 'print' should exist in real builtins
        result = deserializer.try_generating_specific_function(call)
        assert result == "assign_stmt"
        ast_assign_mock.assert_called_once_with(call)

    # --- Patch builtins to test 'set', 'list', 'tuple', 'dict' branches ---
    with (
        patch("pynguin.large_language_model.parsing.deserializer.__builtins__", {}),
        patch.object(deserializer, "create_stmt_from_collection", return_value="collection_stmt"),
    ):
        # Case 2: "set"
        call = call_with_func("set", args=[ast.Constant(value=1)])
        assert deserializer.try_generating_specific_function(call) == "collection_stmt"

        # Case 3: "list"
        call = call_with_func("list", args=[ast.Constant(value=2)])
        assert deserializer.try_generating_specific_function(call) == "collection_stmt"

        # Case 4: "tuple"
        call = call_with_func("tuple", args=[ast.Constant(value=3)])
        assert deserializer.try_generating_specific_function(call) == "collection_stmt"

        # Case 5: "dict" (valid dict node)
        dict_node = ast.Dict(keys=[ast.Constant(value="k")], values=[ast.Constant(value="v")])
        call = call_with_func("dict", args=[dict_node])
        assert deserializer.try_generating_specific_function(call) == "collection_stmt"

    # --- Case 6: "dict" with invalid arg (triggers AttributeError) ---
    with patch("pynguin.large_language_model.parsing.deserializer.__builtins__", {}):
        bad_arg = ast.Constant(value="not_a_dict")
        call = call_with_func("dict", args=[bad_arg])
        assert deserializer.try_generating_specific_function(call) is None

    # --- Case 7: unknown function name (fallback to None) ---
    call = call_with_func("custom_func")
    assert deserializer.try_generating_specific_function(call) is None

    # --- Case 8: call.func lacks .id (triggers AttributeError) ---
    call = ast.Call(func=ast.Constant(value="broken"), args=[], keywords=[])
    assert deserializer.try_generating_specific_function(call) is None


def make_dummy_type_and_elems():
    return "fake_type", ["ref1", "ref2"]


def test_create_set_statement(deserializer):
    deserializer._testcase = MagicMock()
    coll_node = ast.Set(elts=[ast.Constant(value=1)])

    coll_elems_type, coll_elems = make_dummy_type_and_elems()
    stmt_obj = deserializer.create_specific_collection_stmt(coll_node, coll_elems_type, coll_elems)

    assert stmt_obj is not None
    assert stmt_obj.__class__.__name__ == "SetStatement"


def test_create_dict_statement(deserializer):
    coll_node = ast.Dict(keys=[], values=[])

    kv_pairs = [(MagicMock(), MagicMock())]
    stmt_obj = deserializer.create_specific_collection_stmt(coll_node, "dict_type", kv_pairs)

    assert stmt_obj is not None
    assert stmt_obj.__class__.__name__ == "DictStatement"


def test_create_tuple_statement(deserializer):
    deserializer._testcase = MagicMock()
    coll_node = ast.Tuple(elts=[ast.Constant(value=1)], ctx=ast.Load())

    coll_elems_type, coll_elems = make_dummy_type_and_elems()
    stmt_obj = deserializer.create_specific_collection_stmt(coll_node, coll_elems_type, coll_elems)

    assert stmt_obj is not None
    assert stmt_obj.__class__.__name__ == "TupleStatement"


def test_create_statement_unknown_node_type(deserializer):
    class CustomNode(ast.AST):  # Not List/Set/Dict/Tuple
        pass

    coll_node = CustomNode()
    coll_elems_type, coll_elems = make_dummy_type_and_elems()
    stmt_obj = deserializer.create_specific_collection_stmt(coll_node, coll_elems_type, coll_elems)

    assert stmt_obj is None


def test_create_assert_stmt_all_branches(deserializer):
    # Patch _get_source_reference to always return a mock reference
    ref = MagicMock()
    with (
        patch.object(deserializer, "_get_source_reference", return_value=ref),
        patch.object(deserializer, "create_assertion", return_value=MagicMock()),
        patch(
            "pynguin.large_language_model.parsing.deserializer.ass.IsInstanceAssertion",
            return_value="isinstance_assertion",
        ),
    ):
        # Branch 1: assert on variable equals constant
        assert_node = MagicMock(spec=ast.Assert)
        assert_node.left = MagicMock(spec=ast.Name)
        assert_node.ops = [ast.Eq()]
        assert_node.comparators = [ast.Constant(value=5)]
        result = deserializer.create_assert_stmt(assert_node)
        assert result is not None
        assert isinstance(result, tuple)
        assert result[0] is not None
        assert result[1] == ref

        # Branch 2: isinstance assert
        isinstance_code = "assert isinstance(x, int)"
        isinstance_node = ast.parse(isinstance_code).body[0]
        result = deserializer.create_assert_stmt(isinstance_node)
        assert result == ("isinstance_assertion", ref)

        # Branch 3: complex assert with function on LHS (mocked)
        class FakeFunc:
            def __init__(self):
                self.left = MagicMock()
                self.comparators = [MagicMock()]
                self.ops = [ast.Eq()]
                self.left.func = MagicMock()

        complex_node = ast.Assert(test=FakeFunc())
        result = deserializer.create_assert_stmt(complex_node)
        assert result is not None

        # Branch 4: normal binary comparison (assert x == 5) -> else branch
        binary_code = "assert x == 5"
        binary_node = ast.parse(binary_code).body[0]
        result = deserializer.create_assert_stmt(binary_node)
        assert result is not None
        assert isinstance(result, tuple)

        # Branch 4: fallback else branch (with mock structure)
        class Fallback:
            def __init__(self):
                self.left = MagicMock()
                self.comparators = [MagicMock()]
                self.ops = [ast.Eq()]

        fallback_node = ast.Assert(test=Fallback())
        result = deserializer.create_assert_stmt(fallback_node)
        assert result is not None

        # Branch 5: causes AttributeError (invalid structure)
        invalid_node = ast.Assert(test=ast.Constant(value=True))
        result = deserializer.create_assert_stmt(invalid_node)
        assert result is None


def test_create_assertion_with_various_ast_nodes(deserializer):
    source = MagicMock()

    # 1. Constant float → FloatAssertion
    float_node = ast.Constant(value=math.pi)
    result = deserializer.create_assertion(source, float_node)
    assert isinstance(result, FloatAssertion)
    assert result.source == source
    assert result.value == math.pi

    # 2. Constant str → ObjectAssertion
    str_node = ast.Constant(value="hi")
    result = deserializer.create_assertion(source, str_node)
    assert isinstance(result, ObjectAssertion)
    assert result.source == source
    assert result.object == "hi"

    neg_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=5))
    result = deserializer.create_assertion(source, neg_node)
    assert isinstance(result, ObjectAssertion)
    assert result.object == 5

    # 5. Unsupported AST → raises ValueError
    class UnknownNode(ast.AST):
        pass

    with pytest.raises(ValueError, match="Unsupported AST node type"):
        deserializer._extract_value_from_ast(UnknownNode())


def test_create_variable_references_from_call_args(deserializer):
    # Setup mock variable references
    var_ref_a = MagicMock(spec=vr.VariableReference)
    var_ref_b = MagicMock(spec=vr.VariableReference)
    var_ref_c = MagicMock(spec=vr.VariableReference)

    deserializer._ref_dict = {
        "a": var_ref_a,
        "b": var_ref_b,
        "c": var_ref_c,
    }

    # Prepare a mock signature
    param_a = inspect.Parameter("a", inspect.Parameter.POSITIONAL_ONLY)
    param_b = inspect.Parameter("b", inspect.Parameter.VAR_POSITIONAL)
    param_k = inspect.Parameter("k", inspect.Parameter.KEYWORD_ONLY)

    mock_sig = MagicMock()
    mock_sig.signature.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY),
        "a": param_a,
        "b": param_b,
        "k": param_k,
    }

    # Mock callable info
    gen_callable = MagicMock()
    gen_callable.is_method.return_value = True
    gen_callable.is_constructor.return_value = False
    gen_callable.is_classmethod.return_value = False
    gen_callable.inferred_signature = mock_sig

    # AST inputs
    call_args = [
        ast.Name(id="a", ctx=ast.Load()),  # matches param_a
        ast.Starred(value=ast.Name(id="b", ctx=ast.Load()), ctx=ast.Load()),  # matches param_b
    ]

    call_keywords = [ast.keyword(arg="k", value=ast.Name(id="c", ctx=ast.Load()))]

    # Execute
    result = deserializer.create_variable_references_from_call_args(
        call_args, call_keywords, gen_callable
    )

    # Assertions
    assert result is not None
    assert result == {
        "a": var_ref_a,
        "b": var_ref_b,
        "k": var_ref_c,
    }


def test_create_elements_all_paths(deserializer):
    # Mock variable reference for ast.Name case
    mock_ref = MagicMock(name="VarRef")
    deserializer._ref_dict = {"x": mock_ref}

    # Patch all `create_*` methods to return distinct mock objects
    deserializer.create_stmt_from_constant = lambda _: MagicMock(name="const_stmt")
    deserializer.create_stmt_from_unaryop = lambda _: MagicMock(name="unary_stmt")
    deserializer.create_stmt_from_call = lambda _: MagicMock(name="call_stmt")
    deserializer.create_stmt_from_collection = lambda _: MagicMock(name="coll_stmt")
    deserializer._testcase.add_variable_creating_statement = lambda stmt: f"VR_{stmt._mock_name}"

    # AST elements for every branch
    const_node = ast.Constant(value=42)
    unary_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=5))
    call_node = ast.Call(func=ast.Name(id="foo", ctx=ast.Load()), args=[], keywords=[])
    list_node = ast.List(elts=[], ctx=ast.Load())
    name_node = ast.Name(id="x", ctx=ast.Load())

    result = deserializer.create_elements([const_node, unary_node, call_node, list_node, name_node])

    assert result == [
        "VR_const_stmt",
        "VR_unary_stmt",
        "VR_call_stmt",
        "VR_coll_stmt",
        mock_ref,
    ]


@pytest.mark.parametrize(
    "obj_type, match_name, in_ref_dict, should_match",
    [
        ("constructor", "MyClass", False, True),  # ✅ constructor match
        ("method", "my_method", True, True),  # ✅ method match
        ("function", "my_func", False, True),  # ✅ function match
        ("unknown", "nothing", False, False),  # ❌ no match
    ],
)
def test_find_gen_callable_variants(  # noqa: PLR0917
    test_cluster, deserializer, obj_type, match_name, in_ref_dict, should_match
):
    deserializer._ref_dict = {"obj": MagicMock(type=AnyType())} if in_ref_dict else {}

    # Create fake ast.Call node depending on type
    if obj_type in {"method", "constructor"}:
        func = ast.Attribute(
            value=ast.Name(id="obj", ctx=ast.Load()), attr=match_name, ctx=ast.Load()
        )
    else:
        func = ast.Name(id=match_name, ctx=ast.Load())
    call = ast.Call(func=func, args=[], keywords=[])

    # Mock object to test
    if obj_type == "constructor":
        obj = create_autospec(GenericConstructor)
        obj.owner = f"package.{match_name}"  # owner gets split
    elif obj_type == "method":
        obj = create_autospec(GenericMethod)
        obj.method_name = match_name
        obj.owner = "SomeClass"
    elif obj_type == "function":
        obj = create_autospec(GenericFunction)
        obj.function_name = match_name
    else:
        obj = MagicMock()

    test_cluster.accessible_objects_under_test = [obj]
    result = deserializer.find_gen_callable(call)

    if should_match:
        assert result == obj
    else:
        assert result is None


def test_add_assert_stmt_all_branches(deserializer):
    get_statement_mock = MagicMock()
    deserializer._testcase = MagicMock()
    deserializer._testcase.get_statement.return_value = get_statement_mock

    assertion = MagicMock()

    # --- Case 1: create_assert_stmt returns None ---
    deserializer.create_assert_stmt = lambda _: None
    assert not deserializer.add_assert_stmt(ast.Assert())

    # --- Case 2: VariableReference with stmt_position ---
    var_ref = MagicMock(spec=vr.VariableReference)
    var_ref.get_statement_position.return_value = 10
    deserializer.create_assert_stmt = lambda _: (assertion, var_ref)
    assert deserializer.add_assert_stmt(ast.Assert())

    # --- Case 3: FieldReference with stmt_position ---
    inner_ref = MagicMock()
    inner_ref.get_statement_position.return_value = 99
    field_ref = MagicMock(spec=vr.FieldReference)
    field_ref.get_variable_reference.return_value = inner_ref
    deserializer.create_assert_stmt = lambda _: (assertion, field_ref)
    assert deserializer.add_assert_stmt(ast.Assert())

    # --- Case 4: VariableReference with stmt_position = None ---
    no_stmt_ref = MagicMock(spec=vr.VariableReference)
    no_stmt_ref.get_statement_position.return_value = None
    deserializer.create_assert_stmt = lambda _: (assertion, no_stmt_ref)
    assert deserializer.add_assert_stmt(ast.Assert())

    # ✅ Assert call sequence
    assert deserializer._testcase.get_statement.call_args_list == [call(10), call(99)]
    assert get_statement_mock.add_assertion.call_count == 2


@pytest.mark.parametrize(
    "value, expected_type",
    [
        (None, stmt.NoneStatement),
        (True, stmt.BooleanPrimitiveStatement),
        (42, stmt.IntPrimitiveStatement),
        (math.pi, stmt.FloatPrimitiveStatement),
        ("hello", stmt.StringPrimitiveStatement),
        (b"bytes", stmt.BytesPrimitiveStatement),
        (complex(1, 2), None),
    ],
)
def test_create_stmt_from_constant(value, expected_type, deserializer):
    constant_node = ast.Constant(value=value)
    result = deserializer.create_stmt_from_constant(constant_node)

    if expected_type is None:
        assert result is None
    else:
        assert isinstance(result, expected_type)


def test_create_stmt_from_unaryop_int_negative(deserializer):
    node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=42))
    result = deserializer.create_stmt_from_unaryop(node)

    assert isinstance(result, stmt.IntPrimitiveStatement)
    assert result.value == -42


def test_create_assert_stmt_all_paths(deserializer):
    # Setup deserializer
    test_case = MagicMock()
    deserializer._testcase = test_case

    # Mock ref_dict entries for all variables used
    mock_ref = MagicMock(spec=VariableReference)
    mock_ref.get_statement_position.return_value = 0
    mock_ref.type = Instance(TypeInfo(dict))
    deserializer._ref_dict = {
        "x": mock_ref,
        "y": mock_ref,
        "z": mock_ref,
        "obj": mock_ref,
    }

    # Create a field reference return for .attr
    mock_attr_ref = MagicMock(spec=FieldReference)
    mock_attr_ref.get_variable_reference.return_value = mock_ref
    deserializer._get_source_reference = MagicMock(
        side_effect=[
            mock_ref,  # for assert x == 1
            mock_ref,  # for isinstance(x, int)
            mock_ref,  # for assert str(x) == '1'
            mock_ref,  # for fallback
        ]
    )

    # Code with all assertion shapes
    code = """
def test_all_assertions():
    x = 1
    y = 2
    z = 3
    obj = "text"
    assert x == 1
    assert isinstance(x, int)
    assert x is None
"""

    # Parse and run the deserializer
    module = ast.parse(code)
    function = module.body[0]
    assert isinstance(function, ast.FunctionDef)

    # Visit all assert statements manually
    for statement in function.body:
        if isinstance(statement, ast.Assert):
            assert deserializer.add_assert_stmt(statement) is True


def test_create_stmt_from_collection(deserializer):
    module = ast.parse(
        textwrap.dedent("""
        def test_collections():
            a = [1, 2, 3]
            b = {"x": 1, "y": 2}
    """)
    )
    fn_body = module.body[0].body
    list_node = fn_body[0].value  # [1, 2, 3]
    dict_node = fn_body[1].value  # {"x": 1, "y": 2}

    # Execute method under test
    list_stmt = deserializer.create_stmt_from_collection(list_node)
    dict_stmt = deserializer.create_stmt_from_collection(dict_node)

    assert isinstance(list_stmt, stmt.ListStatement)
    assert isinstance(dict_stmt, stmt.DictStatement)


def test_assemble_stmt_from_gen_callable_function(deserializer):
    # Setup deserializer
    deserializer._testcase = MagicMock()
    deserializer._ref_dict = {}

    # Setup callable: just a mock GenericFunction
    gen_callable = create_autospec(GenericFunction)

    # AST Call with 1 argument
    call = ast.Call(
        func=ast.Name(id="foo", ctx=ast.Load()),
        args=[ast.Name(id="x", ctx=ast.Load())],
        keywords=[],
    )

    # Pretend we resolved the call args
    deserializer.create_variable_references_from_call_args = lambda *_, **__: {"x": MagicMock()}

    # Act
    result = deserializer.assemble_stmt_from_gen_callable(gen_callable, call)

    # Assert
    assert isinstance(result, stmt.FunctionStatement)


def test_extract_value_from_ast_all_cases(deserializer):
    # List of constants
    list_node = ast.List(elts=[ast.Constant(value=1), ast.Constant(value=2)], ctx=ast.Load())
    assert deserializer._extract_value_from_ast(list_node) == [1, 2]

    # Tuple of constants
    tuple_node = ast.Tuple(elts=[ast.Constant(value="a"), ast.Constant(value="b")], ctx=ast.Load())
    assert deserializer._extract_value_from_ast(tuple_node) == ("a", "b")

    # Set of constants
    set_node = ast.Set(elts=[ast.Constant(value=3), ast.Constant(value=4)])
    assert deserializer._extract_value_from_ast(set_node) == {3, 4}

    # Dict with constants
    dict_node = ast.Dict(keys=[ast.Constant(value="k")], values=[ast.Constant(value="v")])
    assert deserializer._extract_value_from_ast(dict_node) == {"k": "v"}

    # Constant node
    const_node = ast.Constant(value=42)
    assert deserializer._extract_value_from_ast(const_node) == 42

    # Name returns None
    name_node = ast.Name(id="x", ctx=ast.Load())
    assert deserializer._extract_value_from_ast(name_node) is None

    # Call returns None
    call_node = ast.Call(func=ast.Name(id="foo", ctx=ast.Load()), args=[], keywords=[])
    assert deserializer._extract_value_from_ast(call_node) is None

    # UnaryOp USub (negative)
    usub_node = ast.UnaryOp(op=ast.USub(), operand=ast.Constant(value=5))
    assert deserializer._extract_value_from_ast(usub_node) == -5

    # UnaryOp UAdd (positive)
    uadd_node = ast.UnaryOp(op=ast.UAdd(), operand=ast.Constant(value=7))
    assert deserializer._extract_value_from_ast(uadd_node) == 7

    # Unsupported node type
    with pytest.raises(ValueError, match="Unsupported AST node type"):
        deserializer._extract_value_from_ast(ast.BinOp())  # Not handled
