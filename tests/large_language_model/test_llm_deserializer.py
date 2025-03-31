import ast

from unittest.mock import MagicMock

import pytest

from pynguin.large_language_model.parsing.deserializer import AstToTestCaseTransformer
from pynguin.large_language_model.parsing.deserializer import StatementDeserializer
from pynguin.large_language_model.parsing.deserializer import (
    deserialize_code_to_testcases,
)
from pynguin.testcase import defaulttestcase as dtc


@pytest.fixture
def test_cluster():
    mock_cluster = MagicMock()

    mock_type_info = MagicMock()

    mock_type_system = MagicMock()
    mock_type_system.to_type_info.return_value = mock_type_info

    mock_cluster.type_system = mock_type_system
    mock_cluster.accessible_objects_under_test = []

    return mock_cluster


def test_assign_constant(test_cluster):
    deserializer = StatementDeserializer(test_cluster)
    assign_node = ast.parse("x = 42").body[0]  # ast.Assign
    assert deserializer.add_assign_stmt(assign_node)
    testcase = deserializer.get_test_case()
    assert isinstance(testcase, dtc.DefaultTestCase)
    assert len(testcase.statements) == 1


def test_unary_op_assign(test_cluster):
    deserializer = StatementDeserializer(test_cluster)
    assign_node = ast.parse("y = -10").body[0]
    assert deserializer.add_assign_stmt(assign_node)
    assert isinstance(deserializer.get_test_case(), dtc.DefaultTestCase)


def test_collection_assign_list(test_cluster):
    deserializer = StatementDeserializer(test_cluster)
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
