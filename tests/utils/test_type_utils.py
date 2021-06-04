#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
from typing import Any, Dict, List, Set, Tuple, Union
from unittest.mock import MagicMock, patch

import pytest

from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.type_utils import (
    class_in_module,
    function_in_module,
    given_exception_matches,
    is_assignable_to,
    is_bytes,
    is_collection_type,
    is_none_type,
    is_numeric,
    is_optional_parameter,
    is_primitive_type,
    is_string,
    is_type_unknown,
    wrap_var_param_type,
)


@pytest.mark.parametrize(
    "type_, result",
    [
        pytest.param(int, True),
        pytest.param(float, True),
        pytest.param(str, True),
        pytest.param(bool, True),
        pytest.param(complex, True),
        pytest.param(type, False),
        pytest.param(None, False),
    ],
)
def test_is_primitive_type(type_, result):
    assert is_primitive_type(type_) == result


@pytest.mark.parametrize(
    "type_, result",
    [
        pytest.param(type(None), True),
        pytest.param(None, False),
        pytest.param(str, False),
    ],
)
def test_is_none_type(type_, result):
    assert is_none_type(type_) == result


@pytest.mark.parametrize(
    "type_,result",
    [pytest.param(None, True), pytest.param(MagicMock, False)],
)
def test_is_type_unknown(type_, result):
    assert is_type_unknown(type_) == result


@pytest.mark.parametrize(
    "module, result",
    [pytest.param("wrong_module", False), pytest.param("unittest.mock", True)],
)
def test_class_in_module(module, result):
    predicate = class_in_module(module)
    assert predicate(MagicMock) == result


@pytest.mark.parametrize(
    "module, result",
    [pytest.param("wrong_module", False), pytest.param("unittest.mock", True)],
)
def test_function_in_module(module, result):
    predicate = function_in_module(module)
    assert predicate(patch) == result


@pytest.mark.parametrize(
    "from_type,to_type,result",
    [
        pytest.param(int, int, True),
        pytest.param(float, Union[int, float], True),
        pytest.param(float, int, False),
        pytest.param(float, Union[str, int], False),
        pytest.param(float, Any, True),
        pytest.param(int, Any, True),
    ],
)
def test_is_assignable_to(from_type, to_type, result):
    assert is_assignable_to(from_type, to_type) == result


@pytest.mark.parametrize(
    "value, result",
    [(5, True), (5.5, True), ("test", False), (None, False)],
)
def test_is_numeric(value, result):
    assert is_numeric(value) == result


@pytest.mark.parametrize(
    "value, result",
    [(5, False), (5.5, False), ("test", True), (None, False)],
)
def test_is_string(value, result):
    assert is_string(value) == result


@pytest.mark.parametrize(
    "value, result",
    [(b"5", True), ("foo", False), (bytearray("test", "ascii"), True), (None, False)],
)
def test_is_bytes(value, result):
    assert is_bytes(value) == result


@pytest.mark.parametrize(
    "param_name,result",
    [
        pytest.param("normal", False),
        pytest.param("args", True),
        pytest.param("kwargs", True),
        pytest.param("default", True),
    ],
)
def test_should_skip_parameter(param_name, result):
    def inner_func(normal: str, *args, default="foo", **kwargs):
        pass  # pragma: no cover

    inf_sig = MagicMock(InferredSignature, signature=inspect.signature(inner_func))
    assert is_optional_parameter(inf_sig, param_name) == result


@pytest.mark.parametrize(
    "kind,type_,result",
    [
        pytest.param(inspect.Parameter.VAR_POSITIONAL, None, List[Any]),
        pytest.param(inspect.Parameter.VAR_POSITIONAL, str, List[str]),
        pytest.param(inspect.Parameter.VAR_KEYWORD, None, Dict[str, Any]),
        pytest.param(inspect.Parameter.VAR_KEYWORD, str, Dict[str, str]),
        pytest.param(inspect.Parameter.POSITIONAL_OR_KEYWORD, Dict, Dict),
    ],
)
def test_wrap_var_param_type(kind, type_, result):
    assert wrap_var_param_type(type_, kind) == result


@pytest.mark.parametrize(
    "type_,result",
    [
        pytest.param(list, True),
        pytest.param(set, True),
        pytest.param(dict, True),
        pytest.param(tuple, True),
        pytest.param(List[str], True),
        pytest.param(Set[str], True),
        pytest.param(Tuple[str], True),
        pytest.param(Dict[str, str], True),
        pytest.param(str, False),
    ],
)
def test_is_collection_type(type_, result):
    assert is_collection_type(type_) == result


@pytest.mark.parametrize(
    "exception,ex_match,result",
    [
        pytest.param(ValueError, ValueError, True),
        pytest.param(ValueError(), ValueError, True),
        pytest.param(ValueError(), Exception, True),
        pytest.param(ValueError(), NameError, False),
    ],
)
def test_given_exception_matches(exception, ex_match, result):
    assert given_exception_matches(exception, ex_match) == result
