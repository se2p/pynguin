#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.11."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation.version.common import InstrumentationArgument
from pynguin.instrumentation.version.common import InstrumentationClassDeref
from pynguin.instrumentation.version.common import InstrumentationConstantLoad
from pynguin.instrumentation.version.common import InstrumentationDeref
from pynguin.instrumentation.version.common import InstrumentationFastLoad
from pynguin.instrumentation.version.common import InstrumentationGlobalLoad
from pynguin.instrumentation.version.common import InstrumentationInstructionsGenerator
from pynguin.instrumentation.version.common import InstrumentationMethodCall
from pynguin.instrumentation.version.common import InstrumentationNameLoad
from pynguin.instrumentation.version.common import InstrumentationSetupAction
from pynguin.instrumentation.version.common import InstrumentationStackValue


if TYPE_CHECKING:
    from bytecode.instr import _UNSET

from .python3_10 import *  # noqa: F403


class Python311InstrumentationInstructionsGenerator(InstrumentationInstructionsGenerator):
    """Generates instrumentation instructions for Python 3.11."""

    @classmethod
    def generate_setup_instructions(  # noqa: D102
        cls,
        setup_action: InstrumentationSetupAction,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match setup_action:
            case (
                InstrumentationSetupAction.NO_ACTION
                | InstrumentationSetupAction.COPY_FIRST
                | InstrumentationSetupAction.COPY_FIRST_TWO
            ):
                # We can just directly copy simple values from the right place
                # in Python 3.11 so no need to duplicate them in the setup.
                return ()
            case InstrumentationSetupAction.COPY_FIRST_SHIFT_DOWN_TWO:
                return (
                    cf.ArtificialInstr("SWAP", 2, lineno=lineno),
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_SECOND:
                # We need to copy the second value from the stack because
                # it will be placed on the first position in the stack
                return (cf.ArtificialInstr("COPY", 2, lineno=lineno),)
            case InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_TWO:
                return (
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 2, lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_THREE:
                return (
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 4, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 3, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 2, lineno=lineno),
                )
            case InstrumentationSetupAction.ADD_FIRST_TWO:
                return (
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("COPY", 2, lineno=lineno),
                    cf.ArtificialInstr("BINARY_OP", 0, lineno=lineno),
                )
            case InstrumentationSetupAction.ADD_FIRST_TWO_REVERSED:
                return (
                    cf.ArtificialInstr("COPY", 1, lineno=lineno),
                    cf.ArtificialInstr("COPY", 3, lineno=lineno),
                    cf.ArtificialInstr("BINARY_OP", 0, lineno=lineno),
                )
            case _:
                raise ValueError(f"Unsupported instrumentation setup action: {setup_action}.")

    @classmethod
    def _generate_argument_instruction(
        cls,
        arg: InstrumentationArgument,
        position: int,
        lineno: int | _UNSET | None,
    ) -> cf.ArtificialInstr:
        match arg:
            case InstrumentationConstantLoad(value):
                return cf.ArtificialInstr("LOAD_CONST", value, lineno=lineno)  # type: ignore[arg-type]
            case InstrumentationFastLoad(name):
                return cf.ArtificialInstr("LOAD_FAST", name, lineno=lineno)
            case InstrumentationNameLoad(name):
                return cf.ArtificialInstr("LOAD_NAME", name, lineno=lineno)
            case InstrumentationGlobalLoad(name):
                return cf.ArtificialInstr("LOAD_GLOBAL", name, lineno=lineno)
            case InstrumentationDeref(name):
                return cf.ArtificialInstr("LOAD_DEREF", name, lineno=lineno)
            case InstrumentationClassDeref(name):
                return cf.ArtificialInstr("LOAD_CLASSDEREF", name, lineno=lineno)
            case InstrumentationStackValue():
                return cf.ArtificialInstr("COPY", position + 2 + arg.value, lineno=lineno)

    @classmethod
    def generate_method_call_instructions(  # noqa: D102
        cls,
        method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        return (
            cf.ArtificialInstr("LOAD_CONST", method_call.self, lineno=lineno),
            cf.ArtificialInstr("LOAD_METHOD", method_call.method_name, lineno=lineno),
            *(
                cls._generate_argument_instruction(arg, position, lineno=lineno)
                for position, arg in enumerate(method_call.args)
            ),
            cf.ArtificialInstr("PRECALL", len(method_call.args), lineno=lineno),
            cf.ArtificialInstr("CALL", len(method_call.args), lineno=lineno),
        )

    @classmethod
    def generate_teardown_instructions(  # noqa: D102
        cls,
        setup_action: InstrumentationSetupAction,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match setup_action:
            case (
                InstrumentationSetupAction.NO_ACTION
                | InstrumentationSetupAction.COPY_FIRST
                | InstrumentationSetupAction.COPY_FIRST_TWO
            ):
                # We did not copy anything in the setup so we do not need to remove anything
                # except the return value of the method call.
                return (cf.ArtificialInstr("POP_TOP", lineno=lineno),)
            case (
                InstrumentationSetupAction.COPY_FIRST_SHIFT_DOWN_TWO
                | InstrumentationSetupAction.COPY_SECOND
                | InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_TWO
                | InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_THREE
                | InstrumentationSetupAction.ADD_FIRST_TWO
                | InstrumentationSetupAction.ADD_FIRST_TWO_REVERSED
            ):
                # We need to remove the value we copied in the setup and the return value
                # of the method call.
                return (
                    cf.ArtificialInstr("POP_TOP", lineno=lineno),
                    cf.ArtificialInstr("POP_TOP", lineno=lineno),
                )
            case _:
                raise ValueError(f"Unsupported instrumentation setup action: {setup_action}.")
