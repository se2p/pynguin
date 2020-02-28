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
import inspect
from typing import Union

import pytest

from pynguin.typeinference.strategy import InferredSignature


def _dummy(x: int, y: int) -> int:
    return x * y


@pytest.fixture
def signature():
    return inspect.signature(_dummy)


@pytest.fixture
def inferred_signature(signature):
    return InferredSignature(
        signature=signature, parameters={"x": int, "y": int}, return_type=int,
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
