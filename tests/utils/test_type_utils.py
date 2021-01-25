#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
from typing import Any, Union
from unittest.mock import MagicMock, patch

import pytest

from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.type_utils import (
    class_in_module,
    function_in_module,
    is_assignable_to,
    is_none_type,
    is_numeric,
    is_primitive_type,
    is_string,
    is_type_unknown,
    should_skip_parameter,
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
    "param_name,result",
    [
        pytest.param("normal", False),
        pytest.param("args", True),
        pytest.param("kwargs", True),
    ],
)
def test_should_skip_parameter(param_name, result):
    def inner_func(normal: str, *args, **kwargs):
        pass

    inf_sig = MagicMock(InferredSignature, signature=inspect.signature(inner_func))
    assert should_skip_parameter(inf_sig, param_name) == result
