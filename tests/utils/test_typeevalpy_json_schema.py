#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for the TypeEvalPy JSON generation."""
from inspect import Signature
from unittest.mock import MagicMock

import pytest

from astroid import FunctionDef
from astroid import parse

import pynguin.configuration as config

from pynguin.analyses.typesystem import InferredSignature
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import TypeInfo
from pynguin.analyses.typesystem import UnionType
from pynguin.utils.typeevalpy_json_schema import TypeEvalPySchemaFunctionReturn
from pynguin.utils.typeevalpy_json_schema import TypeEvalPySchemaParameter
from pynguin.utils.typeevalpy_json_schema import convert_parameter
from pynguin.utils.typeevalpy_json_schema import convert_return


@pytest.fixture(scope="session")
def function_node() -> FunctionDef:
    code = """
def fun(a: int, b: float | complex) -> str:
    return f"{a} | {b}"
"""
    module = parse(code)
    return module.body[0]


@pytest.fixture(scope="session")
def file_name() -> str:
    return "test.py"


@pytest.fixture(scope="session")
def signature() -> InferredSignature:
    signature = MagicMock(Signature)
    signature.return_value.return_annotation.return_value = str
    inferred_signature = InferredSignature(
        signature=signature,
        original_return_type=Instance(TypeInfo(str)),
        original_parameters={
            "a": Instance(TypeInfo(int)),
            "b": UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(complex)))),
        },
        type_system=MagicMock(),
    )
    inferred_signature.current_guessed_parameters = {
        "a": [Instance(TypeInfo(int))],
        "b": [UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(complex))))],
    }
    return inferred_signature


@pytest.fixture(scope="session")
def function_name(function_node) -> str:
    return function_node.name


def test_convert_return(file_name, function_node, signature, function_name):
    config.configuration.type_inference.type_tracing = True
    actual = convert_return(
        file_name, function_node, signature, function_name, is_function=True
    )
    expected = TypeEvalPySchemaFunctionReturn(
        file=file_name,
        line_number=2,
        col_offset=5,
        type=["str"],
        function=function_name,
    )
    assert actual == expected


def test_convert_parameter(file_name, function_node, signature, function_name):
    config.configuration.type_inference.type_tracing = True
    actual = convert_parameter(
        file_name, function_node, "b", signature, function_name, None
    )
    expected = TypeEvalPySchemaParameter(
        file=file_name,
        line_number=2,
        col_offset=17,
        type=["complex", "float"],
        function=function_name,
        parameter="b",
    )
    assert actual == expected
