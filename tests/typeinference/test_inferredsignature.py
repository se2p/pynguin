#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
