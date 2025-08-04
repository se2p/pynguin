#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import dis
import sys

from itertools import starmap
from opcode import HAVE_ARGUMENT
from opcode import opmap
from unittest.mock import MagicMock

import pytest

from bytecode import Bytecode

from pynguin.instrumentation.version import stack_effects
from pynguin.instrumentation.version.common import InstrumentationConstantLoad
from pynguin.instrumentation.version.common import InstrumentationMethodCall
from pynguin.instrumentation.version.common import InstrumentationSetupAction
from pynguin.instrumentation.version.common import InstrumentationStackValue
from pynguin.instrumentation.version.common import before


if sys.version_info >= (3, 11):
    from pynguin.instrumentation.version.python3_11 import (
        Python311InstrumentationInstructionsGenerator as InstrumentationInstructionsGenerator,
    )
elif sys.version_info >= (3, 10):  # noqa: UP036
    from pynguin.instrumentation.version.python3_10 import (
        Python310InstrumentationInstructionsGenerator as InstrumentationInstructionsGenerator,
    )
else:
    raise ImportError(
        "This module requires Python 3.10 or higher. "
        "Please upgrade your Python version to use this feature."
    )
from tests.utils.version import only_3_10


@only_3_10
@pytest.mark.parametrize(
    "op",
    [pytest.param(op) for op in opmap.values() if op < HAVE_ARGUMENT],
)
def test_argument_less_opcodes(op):
    """Test argument less opcode stack effects."""
    pops, pushes = stack_effects(op, None)
    expected = dis.stack_effect(op)

    assert expected == (pushes - pops)


def _conditional_combinations() -> list[tuple[int, int, bool]]:
    """Create a list of all combinations to call a conditional opcode's stack effect."""
    args = [0, 1]

    # (opcode, argument, jump)  # noqa: ERA001
    combinations: list[tuple[int, int, bool]] = []
    for op in opmap.values():
        if op <= HAVE_ARGUMENT or op is opmap.get("SETUP_ASYNC_WITH"):
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
    pops, pushes = stack_effects(op, arg, jump=jump)
    expected = dis.stack_effect(op, arg, jump=jump)

    assert expected == (pushes - pops)


@only_3_10
def test_async_setup_throws_exception():
    with pytest.raises(AssertionError):
        stack_effects(opmap["SETUP_ASYNC_WITH"], 0)


def test_convert_instrumentation_method_call_with_constant():
    def foo():
        return

    called = False

    def method(a: int, b: bool) -> None:  # noqa: FBT001
        nonlocal called
        called = True

        assert a == 42
        assert b

    mock = MagicMock()
    mock.method = method

    bytecode = Bytecode.from_code(foo.__code__)
    bytecode[before(-1)] = InstrumentationInstructionsGenerator.generate_method_call_instructions(
        InstrumentationMethodCall(
            mock,
            method.__name__,
            (
                InstrumentationConstantLoad(value=42),
                InstrumentationConstantLoad(value=True),
            ),
        ),
        1,
    )
    foo.__code__ = bytecode.to_code()

    foo()

    assert called


def test_convert_instrumentation_method_call_with_stack_argument():
    def foo():
        return 24

    called = False

    def method(a: int, b: int) -> None:
        nonlocal called
        called = True

        assert a == 42
        assert b == 24

    mock = MagicMock()
    mock.method = method

    bytecode = Bytecode.from_code(foo.__code__)
    bytecode[before(-1)] = InstrumentationInstructionsGenerator.generate_instructions(
        InstrumentationSetupAction.COPY_FIRST,
        InstrumentationMethodCall(
            mock,
            method.__name__,
            (
                InstrumentationConstantLoad(value=42),
                InstrumentationStackValue.FIRST,
            ),
        ),
        1,
    )
    foo.__code__ = bytecode.to_code()

    foo()

    assert called


def test_convert_instrumentation_method_call_with_multiple_stack_arguments():
    CONSTANT = 3  # noqa: N806

    def foo():
        return 1 + CONSTANT

    called = False

    def method(a: int, b: int, c: int, d: int) -> None:
        nonlocal called
        called = True

        assert a == 4
        assert b == 3
        assert c == 2
        assert d == 1

    mock = MagicMock()
    mock.method = method

    bytecode = Bytecode.from_code(foo.__code__)
    bytecode[before(-2)] = InstrumentationInstructionsGenerator.generate_instructions(
        InstrumentationSetupAction.COPY_FIRST_TWO,
        InstrumentationMethodCall(
            mock,
            method.__name__,
            (
                InstrumentationConstantLoad(value=4),
                InstrumentationStackValue.FIRST,
                InstrumentationConstantLoad(value=2),
                InstrumentationStackValue.SECOND,
            ),
        ),
        1,
    )
    foo.__code__ = bytecode.to_code()

    foo()

    assert called
