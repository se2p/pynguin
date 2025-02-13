#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for the TypeEvalPy JSON generation."""

import json

from collections.abc import Callable
from inspect import Signature
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest

from astroid import FunctionDef
from astroid import parse

import pynguin.configuration as config

from pynguin.analyses.module import TypeGuessingStats
from pynguin.analyses.module import _CallableData
from pynguin.analyses.typesystem import InferredSignature
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import TypeInfo
from pynguin.analyses.typesystem import UnionType
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.typeevalpy_json_schema import TypeEvalPySchemaFunctionReturn
from pynguin.utils.typeevalpy_json_schema import TypeEvalPySchemaParameter
from pynguin.utils.typeevalpy_json_schema import convert_parameter
from pynguin.utils.typeevalpy_json_schema import convert_return
from pynguin.utils.typeevalpy_json_schema import provide_json


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
    actual = convert_return(file_name, function_node, signature, function_name, is_function=True)
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
    actual = convert_parameter(file_name, function_node, "b", signature, function_name, None)
    expected = TypeEvalPySchemaParameter(
        file=file_name,
        line_number=2,
        col_offset=17,
        type=["complex", "float"],
        function=function_name,
        parameter="b",
    )
    assert actual == expected


@pytest.fixture(scope="session")
def function_node_kwargs() -> FunctionDef:
    code = """
def fun(a: int, b: float | complex, **kwargs: int) -> str:
    return f"{a} | {b}"
"""
    module = parse(code)
    return module.body[0]


@pytest.fixture(scope="session")
def signature_kwargs() -> InferredSignature:
    signature = MagicMock(Signature)
    signature.return_value.return_annotation.return_value = str
    inferred_signature = InferredSignature(
        signature=signature,
        original_return_type=Instance(TypeInfo(str)),
        original_parameters={
            "a": Instance(TypeInfo(int)),
            "b": UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(complex)))),
            "kwargs": Instance(TypeInfo(int)),
        },
        type_system=MagicMock(),
    )
    inferred_signature.current_guessed_parameters = {
        "a": [Instance(TypeInfo(int))],
        "b": [UnionType((Instance(TypeInfo(float)), Instance(TypeInfo(complex))))],
        "kwargs": [Instance(TypeInfo(int))],
    }
    return inferred_signature


def test_convert_parameter_kwargs(file_name, function_node_kwargs, signature_kwargs, function_name):
    config.configuration.type_inference.type_tracing = True
    actual = convert_parameter(
        file_name, function_node_kwargs, "kwargs", signature_kwargs, function_name, None
    )
    expected = TypeEvalPySchemaParameter(
        file=file_name,
        line_number=2,
        col_offset=39,
        type=["int"],
        function=function_name,
        parameter="kwargs",
    )
    assert actual == expected


def test_provide_json(file_name, function_node, signature, function_name):
    config.configuration.type_inference.type_tracing = True

    accessible = GenericFunction(
        function=Callable[[int, float | complex], str],
        inferred_signature=signature,
        raised_exceptions=set(),
        function_name=function_name,
    )
    accessibles = OrderedSet([accessible])
    function_data = {
        accessible: _CallableData(
            tree=function_node, accessible=accessible, description=None, cyclomatic_complexity=0
        )
    }
    stats = TypeGuessingStats(signature_infos={})

    actual_json = provide_json(file_name, accessibles, function_data, stats)
    expected_json = json.dumps([
        {
            "col_offset": 9,
            "file": file_name,
            "function": function_name,
            "line_number": 2,
            "parameter": "a",
            "type": ["int"],
        },
        {
            "col_offset": 17,
            "file": file_name,
            "function": function_name,
            "line_number": 2,
            "parameter": "b",
            "type": ["complex", "float"],
        },
        {
            "col_offset": 5,
            "file": file_name,
            "function": function_name,
            "line_number": 2,
            "type": ["str"],
        },
    ])

    assert json.loads(actual_json) == json.loads(expected_json)


def test_provide_json_constructor(file_name, function_node, signature):
    config.configuration.type_inference.type_tracing = True

    mock_owner = MagicMock()
    mock_owner.name = "TestClass"

    accessible = GenericConstructor(
        inferred_signature=signature, raised_exceptions=set(), owner=mock_owner
    )
    accessibles = OrderedSet([accessible])
    function_data = {
        accessible: _CallableData(
            tree=function_node, accessible=accessible, description=None, cyclomatic_complexity=0
        )
    }
    stats = TypeGuessingStats(signature_infos={})

    actual_json = provide_json(file_name, accessibles, function_data, stats)
    expected_json = json.dumps([
        {
            "col_offset": 9,
            "file": file_name,
            "function": "TestClass.__init__",
            "line_number": 2,
            "parameter": "a",
            "type": ["int"],
        },
        {
            "col_offset": 17,
            "file": file_name,
            "function": "TestClass.__init__",
            "line_number": 2,
            "parameter": "b",
            "type": ["complex", "float"],
        },
    ])

    assert json.loads(actual_json) == json.loads(expected_json)


def test_provide_json_generic_method(file_name, function_node, signature):
    config.configuration.type_inference.type_tracing = True

    mock_owner = MagicMock()
    mock_owner.name = "TestClass"

    accessible = GenericMethod(
        inferred_signature=signature,
        raised_exceptions=set(),
        owner=mock_owner,
        method_name="test_method",
        method=Callable[[int, float | complex], str],
    )
    accessibles = OrderedSet([accessible])
    function_data = {
        accessible: _CallableData(
            tree=function_node, accessible=accessible, description=None, cyclomatic_complexity=0
        )
    }
    stats = TypeGuessingStats(signature_infos={})

    actual_json = provide_json(file_name, accessibles, function_data, stats)
    expected_json = json.dumps([
        {
            "col_offset": 9,
            "file": "test.py",
            "function": "TestClass.test_method",
            "line_number": 2,
            "parameter": "a",
            "type": ["int"],
        },
        {
            "col_offset": 17,
            "file": "test.py",
            "function": "TestClass.test_method",
            "line_number": 2,
            "parameter": "b",
            "type": ["complex", "float"],
        },
        {
            "col_offset": 1,
            "file": "test.py",
            "function": "TestClass.test_method",
            "line_number": 2,
            "type": ["str"],
        },
    ])

    assert json.loads(actual_json) == json.loads(expected_json)


def test_provide_json_unknown_accessible():
    file_name = "test_file.py"

    class UnknownAccessible:
        pass  # A dummy class to simulate an unknown accessible type

    accessible = UnknownAccessible()  # Instance of unknown type
    accessibles = OrderedSet([accessible])  # Add it to the set
    function_data = {}
    stats = TypeGuessingStats(signature_infos={})

    res = provide_json(file_name, accessibles, function_data, stats)
    assert res == "[]"  # make sure there is no crash


def test_provide_json_not_implemented_error():
    file_name = "test_file.py"

    accessible = Mock(GenericCallableAccessibleObject)
    accessibles = OrderedSet([accessible])  # Add it to the set
    function_data = {}
    stats = TypeGuessingStats(signature_infos={})

    with pytest.raises(NotImplementedError):
        provide_json(file_name, accessibles, function_data, stats)
