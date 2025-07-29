#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import dis

from itertools import starmap
from opcode import HAVE_ARGUMENT
from opcode import opmap

import pytest

from pynguin.instrumentation.version import stack_effect
from tests.utils.version import only_3_10


@only_3_10
@pytest.mark.parametrize(
    "op",
    [pytest.param(op) for op in opmap.values() if op < HAVE_ARGUMENT],
)
def test_argument_less_opcodes(op):
    """Test argument less opcode stack effects."""
    pops, pushes = stack_effect(op, None)
    expected = dis.stack_effect(op)

    assert expected == (pushes - pops)


def _conditional_combinations() -> list[tuple[int, int, bool]]:
    """Create a list of all combinations to call a conditional opcode's stack effect."""
    args = [0, 1]

    # (opcode, argument, jump)  # noqa: ERA001
    combinations: list[tuple[int, int, bool]] = []
    for op in opmap.values():
        if op <= HAVE_ARGUMENT or op is opmap["SETUP_ASYNC_WITH"]:
            continue  # async is not supported
        for arg in args:
            combinations.extend(((op, arg, True), (op, arg, False)))
    return combinations


@only_3_10
@pytest.mark.parametrize(
    "op, arg, jump",
    list(starmap(pytest.param, _conditional_combinations())),
)
def test_conditional_opcodes(op, arg, jump):
    """Test opcodes with arguments and jumps."""
    pops, pushes = stack_effect(op, arg, jump=jump)
    expected = dis.stack_effect(op, arg, jump=jump)

    assert expected == (pushes - pops)


def test_async_setup_throws_exception():
    with pytest.raises(AssertionError):
        stack_effect(opmap["SETUP_ASYNC_WITH"], 0)
