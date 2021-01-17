#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import os
from typing import Any

import pytest

from pynguin.typeinference.stubstrategy import StubInferenceStrategy


def typed_dummy(a, b, c):
    return f"int {a} float {b} any {c}"


def untyped_dummy(a, b, c):
    return f"int {a} float {b} any {c}"


def union_dummy(a, b):
    return a + b


def return_tuple():
    return 23, 42


def return_tuple_no_annotation():
    return 23, 42


class TypedDummy:
    def __init__(self, a):
        self._a = a

    def get_a(self):
        return self._a


class UntypedDummy:
    def __init__(self, a):
        self._a = a

    def get_a(self):
        return self._a


PYI_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")


@pytest.mark.parametrize(
    "method,expected_parameters,expected_return_types",
    [
        pytest.param(typed_dummy, {"a": int, "b": float, "c": None}, str),
        pytest.param(untyped_dummy, {"a": None, "b": None, "c": None}, None),
        # pytest.param(
        #     union_dummy,
        #     {"a": Union[int, float], "b": Union[int, float]},
        #     Union[int, float],
        # ),
        # pytest.param(return_tuple, None, Tuple[int, int]),
        pytest.param(return_tuple_no_annotation, {}, None),
        pytest.param(TypedDummy, {"a": Any}, None),
        pytest.param(UntypedDummy, {"a": None}, None),
    ],
)
def test_infer_type_info(method, expected_parameters, expected_return_types):
    strategy = StubInferenceStrategy(PYI_DIR)
    result = strategy.infer_type_info(method)
    assert result.parameters == expected_parameters
    assert result.return_type == expected_return_types
