# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from typing import Union, Tuple, Any

import pytest

from pynguin.typeinference.typehintsstrategy import TypeHintsInferenceStrategy


def typed_dummy(a: int, b: float, c) -> str:
    return f"int {a} float {b} any {c}"


def untyped_dummy(a, b, c):
    return f"int {a} float {b} any {c}"


def union_dummy(a: Union[int, float], b: Union[int, float]) -> Union[int, float]:
    return a + b


def return_tuple() -> Tuple[int, int]:
    return 23, 42


def return_tuple_no_annotation():
    return 23, 42


class TypedDummy:
    def __init__(self, a: Any) -> None:
        self._a = a

    def get_a(self) -> Any:
        return self._a


class UntypedDummy:
    def __init__(self, a):
        self._a = a

    def get_a(self):
        return self._a


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
        pytest.param(return_tuple, None, Tuple[int, int]),
        pytest.param(return_tuple_no_annotation, None, None),
        pytest.param(TypedDummy, {"a": Any}, None),
        pytest.param(UntypedDummy, {"a": None}, None),
    ],
)
def test_infer_type_info(method, expected_parameters, expected_return_types):
    strategy = TypeHintsInferenceStrategy()
    result = strategy.infer_type_info(method)
    assert result.parameters == expected_parameters
    assert result.return_types == expected_return_types
