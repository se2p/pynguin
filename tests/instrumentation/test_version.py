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
from unittest.mock import MagicMock

import pytest

from bytecode import Bytecode

from pynguin.instrumentation.version import stack_effect
from pynguin.instrumentation.version.common import InstrumentationConstantLoad
from pynguin.instrumentation.version.common import InstrumentationCopy
from pynguin.instrumentation.version.common import InstrumentationMethodCall
from pynguin.instrumentation.version.common import InstrumentationStackValue
from pynguin.instrumentation.version.common import before
from pynguin.instrumentation.version.python3_10 import convert_instrumentation_copy
from pynguin.instrumentation.version.python3_10 import (
    convert_instrumentation_method_call,
)
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


@only_3_10
def test_async_setup_throws_exception():
    with pytest.raises(AssertionError):
        stack_effect(opmap["SETUP_ASYNC_WITH"], 0)


@only_3_10
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

    call = InstrumentationMethodCall(
        mock,
        method.__name__,
        (
            InstrumentationConstantLoad(value=42),
            InstrumentationConstantLoad(value=True),
        ),
    )

    bytecode = Bytecode.from_code(foo.__code__)
    bytecode[before(-1)] = convert_instrumentation_method_call(call, 1)
    foo.__code__ = bytecode.to_code()

    foo()

    assert called


@only_3_10
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

    call = InstrumentationMethodCall(
        mock,
        method.__name__,
        (
            InstrumentationConstantLoad(value=42),
            InstrumentationStackValue.FIRST,
        ),
    )

    bytecode = Bytecode.from_code(foo.__code__)
    bytecode[before(-1)] = (
        *convert_instrumentation_copy(InstrumentationCopy.FIRST, 1),
        *convert_instrumentation_method_call(call, 1),
    )
    foo.__code__ = bytecode.to_code()

    foo()

    assert called


@only_3_10
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

    call = InstrumentationMethodCall(
        mock,
        method.__name__,
        (
            InstrumentationConstantLoad(value=4),
            InstrumentationStackValue.FIRST,
            InstrumentationConstantLoad(value=2),
            InstrumentationStackValue.SECOND,
        ),
    )

    bytecode = Bytecode.from_code(foo.__code__)
    bytecode[before(-2)] = (
        *convert_instrumentation_copy(InstrumentationCopy.TWO_FIRST, 1),
        *convert_instrumentation_method_call(call, 1),
    )
    foo.__code__ = bytecode.to_code()

    foo()

    assert called
