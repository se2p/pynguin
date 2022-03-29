#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
from typing import Any, Union

import pytest

from pynguin.analyses.types import InferredSignature, infer_type_info


def __dummy(x: int, y: int) -> int:
    return x * y  # pragma: no cover


def __func_1(x: int) -> int:
    return x  # pragma: no cover


def __typed_dummy(a: int, b: float, c) -> str:
    return f"int {a} float {b} any {c}"  # pragma: no cover


def __untyped_dummy(a, b, c):
    return f"int {a} float {b} any {c}"  # pragma: no cover


def __union_dummy(a: int | float, b: int | float) -> int | float:
    return a + b  # pragma: no cover


def __return_tuple() -> tuple[int, int]:
    return 23, 42  # pragma: no cover


def __return_tuple_no_annotation():
    return 23, 42  # pragma: no cover


class __TypedDummy:
    def __init__(self, a: Any) -> None:
        self.__a = a  # pragma: no cover

    def get_a(self) -> Any:
        return self.__a  # pragma: no cover


class __UntypedDummy:
    def __init__(self, a):
        self.__a = a  # pragma: no cover

    def get_a(self):
        return self.__a  # pragma: no cover


@pytest.fixture
def signature():
    return inspect.signature(__dummy)


@pytest.fixture
def inferred_signature(signature):
    return InferredSignature(
        signature=signature,
        parameters={"x": int, "y": int},
        return_type=int,
    )


def test_update_parameter_type(inferred_signature):
    inferred_signature.update_parameter_type("x", Union[int, float])
    assert inferred_signature.parameters["x"] == Union[int, float]
    assert inferred_signature.signature.parameters["x"] == inspect.Parameter(
        name="x",
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        annotation=Union[int, float],
    )


def test_update_return_type(inferred_signature):
    inferred_signature.update_return_type(Union[int, float])
    assert inferred_signature.return_type == Union[int, float]
    assert inferred_signature.signature.return_annotation == Union[int, float]


def test_update_non_existing_parameter(inferred_signature):
    with pytest.raises(AssertionError):
        inferred_signature.update_parameter_type("b", bool)


@pytest.mark.parametrize(
    "func, infer_types, expected_parameters, expected_return",
    [
        pytest.param(__func_1, True, {"x": int}, int),
        pytest.param(__func_1, False, {"x": None}, None),
        pytest.param(__typed_dummy, True, {"a": int, "b": float, "c": None}, str),
        pytest.param(__untyped_dummy, True, {"a": None, "b": None, "c": None}, None),
        pytest.param(
            __union_dummy,
            True,
            {"a": Union[int, float], "b": Union[int, float]},
            Union[int, float],
        ),
        pytest.param(__return_tuple, True, {}, tuple[int, int]),
        pytest.param(__return_tuple_no_annotation, True, {}, None),
        pytest.param(__TypedDummy, True, {"a": Any}, type(None)),
        pytest.param(__UntypedDummy, True, {"a": None}, None),
        pytest.param(__TypedDummy, False, {"a": None}, None),
        pytest.param(__UntypedDummy, False, {"a": None}, None),
    ],
)
def test_infer_type_info(func, infer_types, expected_parameters, expected_return):
    result = infer_type_info(func, infer_types)
    assert result.parameters == expected_parameters
    assert result.return_type == expected_return
