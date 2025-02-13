#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import dis

from itertools import starmap

import pytest

import pynguin.slicer.stack.stackeffect as se

from pynguin.utils import opcodes


@pytest.mark.parametrize(
    "op",
    [pytest.param(op) for op in range(90)],  # opcodes up to 90 ignore their argument
)
def test_argument_less_opcodes(op):
    """Test argument less opcode stack effects."""
    if op in opcodes.__dict__.values():
        pops, pushes = se.StackEffect.stack_effect(op, None)
        expected = dis.stack_effect(op)

        assert expected == (pushes - pops)


def _conditional_combinations() -> list[tuple[int, int, bool]]:
    """Create a list of all combinations to call a conditional opcode's stack effect."""
    args = [0, 1]
    conditional_opcodes = range(90, 166)

    # (opcode, argument, jump)  # noqa: ERA001
    combinations: list[tuple[int, int, bool]] = []
    for op in conditional_opcodes:
        if op is opcodes.SETUP_ASYNC_WITH:
            continue  # async is not supported
        for arg in args:
            combinations.extend(((op, arg, True), (op, arg, False)))
    return combinations


@pytest.mark.parametrize(
    "op, arg, jump",
    list(starmap(pytest.param, _conditional_combinations())),
)
def test_conditional_opcodes(op, arg, jump):
    """Test opcodes with arguments and jumps."""
    if op in opcodes.__dict__.values():
        pops, pushes = se.StackEffect.stack_effect(op, arg, jump=jump)
        expected = dis.stack_effect(op, arg, jump=jump)

        assert expected == (pushes - pops)


def test_async_setup_throws_exception():
    with pytest.raises(AssertionError):
        se.StackEffect.stack_effect(opcodes.SETUP_ASYNC_WITH, 0)
