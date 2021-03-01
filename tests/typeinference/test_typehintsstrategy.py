#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Any, Tuple, Union

import pytest

from pynguin.typeinference.typehintsstrategy import TypeHintsInferenceStrategy


def typed_dummy(a: int, b: float, c) -> str:
    return f"int {a} float {b} any {c}"  # pragma: no cover


def untyped_dummy(a, b, c):
    return f"int {a} float {b} any {c}"  # pragma: no cover


def union_dummy(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    return a + b  # pragma: no cover


def return_tuple() -> Tuple[int, int]:
    return 23, 42  # pragma: no cover


def return_tuple_no_annotation():
    return 23, 42  # pragma: no cover


class TypedDummy:
    def __init__(self, a: Any) -> None:
        self._a = a  # pragma: no cover

    def get_a(self) -> Any:
        return self._a  # pragma: no cover


class UntypedDummy:
    def __init__(self, a):
        self._a = a  # pragma: no cover

    def get_a(self):
        return self._a  # pragma: no cover


@pytest.mark.parametrize(
    "method,expected_parameters,expected_return_types",
    [
        pytest.param(typed_dummy, {"a": int, "b": float, "c": None}, str),
        pytest.param(untyped_dummy, {"a": None, "b": None, "c": None}, None),
        pytest.param(
            union_dummy,
            {"a": Union[int, float], "b": Union[int, float]},
            Union[int, float],
        ),
        pytest.param(return_tuple, {}, Tuple[int, int]),
        pytest.param(return_tuple_no_annotation, {}, None),
        pytest.param(TypedDummy, {"a": Any}, type(None)),
        pytest.param(UntypedDummy, {"a": None}, None),
    ],
)
def test_infer_type_info(method, expected_parameters, expected_return_types):
    strategy = TypeHintsInferenceStrategy()
    result = strategy.infer_type_info(method)
    assert result.parameters == expected_parameters
    assert result.return_type == expected_return_types
