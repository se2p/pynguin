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
from typing import Union
from unittest.mock import MagicMock, patch

import pytest

from pynguin.utils.type_utils import (
    is_primitive_type,
    class_in_module,
    function_in_module,
    is_none_type,
    is_assignable_to,
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
def test_is_primitive_type(type_, result):
    assert is_none_type(type_) == result


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
    ],
)
def test_is_assignable_to(from_type, to_type, result):
    assert is_assignable_to(from_type, to_type) == result
