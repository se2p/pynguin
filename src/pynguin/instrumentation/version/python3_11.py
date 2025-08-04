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

from opcode import opmap
from opcode import opname
from typing import ClassVar

from bytecode.instr import _UNSET
from bytecode.instr import UNSET
from bytecode.instr import BinaryOp
from bytecode.instr import Instr

from pynguin.instrumentation import StackEffects
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation import tracer
from pynguin.instrumentation.version import python3_10
from pynguin.instrumentation.version.common import COMPARE_OP_POS
from pynguin.instrumentation.version.common import JUMP_OP_POS
from pynguin.instrumentation.version.common import (
    CheckedCoverageInstrumentationVisitorMethod,
)
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
from pynguin.instrumentation.version.common import before
from pynguin.instrumentation.version.common import to_opcodes

from .python3_10 import ACCESS_OPCODES
from .python3_10 import CLOSURE_LOAD_OPCODES
from .python3_10 import IMPORT_FROM_OPCODES
from .python3_10 import IMPORT_NAME_OPCODES
from .python3_10 import LOAD_DEREF_OPCODES
from .python3_10 import LOAD_FAST_OPCODES
from .python3_10 import LOAD_GLOBAL_OPCODES
from .python3_10 import LOAD_NAME_OPCODES
from .python3_10 import MODIFY_DEREF_OPCODES
from .python3_10 import MODIFY_FAST_OPCODES
from .python3_10 import MODIFY_GLOBAL_OPCODES
from .python3_10 import MODIFY_NAME_OPCODES
from .python3_10 import RETURNING_OPCODES
from .python3_10 import STORE_NAME_OPCODES
from .python3_10 import STORE_OPCODES
from .python3_10 import add_for_loop_no_yield_nodes
from .python3_10 import end_with_explicit_return_none
from .python3_10 import is_conditional_jump


__all__ = [
    "ACCESS_OPCODES",
    "CALL_OPCODES",
    "CLOSURE_LOAD_OPCODES",
    "COND_BRANCH_OPCODES",
    "IMPORT_FROM_OPCODES",
    "IMPORT_NAME_OPCODES",
    "LOAD_DEREF_OPCODES",
    "LOAD_FAST_OPCODES",
    "LOAD_GLOBAL_OPCODES",
    "LOAD_NAME_OPCODES",
    "MEMORY_DEF_OPCODES",
    "MEMORY_USE_OPCODES",
    "MODIFY_DEREF_OPCODES",
    "MODIFY_FAST_OPCODES",
    "MODIFY_GLOBAL_OPCODES",
    "MODIFY_NAME_OPCODES",
    "RETURNING_OPCODES",
    "STORE_NAME_OPCODES",
    "STORE_OPCODES",
    "TRACED_OPCODES",
    "YIELDING_OPCODES",
    "BranchCoverageInstrumentation",
    "CheckedCoverageInstrumentation",
    "DynamicSeedingInstrumentation",
    "LineCoverageInstrumentation",
    "add_for_loop_no_yield_nodes",
    "end_with_explicit_return_none",
    "get_branch_type",
    "is_conditional_jump",
    "stack_effects",
]

# Remaining opcodes
CALL_OPCODES = to_opcodes(
    "CALL",
    "CALL_FUNCTION_EX",
)

YIELDING_OPCODES = to_opcodes("YIELD_VALUE")

OPERATION_OPCODES = python3_10.COMPARE_OPCODES + to_opcodes(
    # Unary operations
    "UNARY_POSITIVE",
    "UNARY_NEGATIVE",
    "UNARY_NOT",
    "UNARY_INVERT",
    "GET_ITER",
    "GET_YIELD_FROM_ITER",
    # Binary and in-place operations
    "BINARY_OP",
)

COND_BRANCH_OPCODES = to_opcodes(
    "POP_JUMP_FORWARD_IF_TRUE",
    "POP_JUMP_BACKWARD_IF_TRUE",
    "POP_JUMP_FORWARD_IF_NOT_NONE",
    "POP_JUMP_BACKWARD_IF_NOT_NONE",
    "JUMP_IF_TRUE_OR_POP",
    "POP_JUMP_FORWARD_IF_FALSE",
    "POP_JUMP_BACKWARD_IF_FALSE",
    "POP_JUMP_FORWARD_IF_NONE",
    "POP_JUMP_BACKWARD_IF_NONE",
    "JUMP_IF_FALSE_OR_POP",
    "FOR_ITER",
)

JUMP_OPCODES = COND_BRANCH_OPCODES + to_opcodes(
    "JUMP_FORWARD",
    "JUMP_BACKWARD",
    "JUMP_BACKWARD_NO_INTERRUPT",
    "BEFORE_WITH",
    "BEFORE_ASYNC_WITH",
)


# Regrouping opcodes
TRACED_OPCODES = (
    OPERATION_OPCODES
    + python3_10.ACCESS_FAST_OPCODES
    + python3_10.ACCESS_NAME_OPCODES
    + python3_10.ACCESS_GLOBAL_OPCODES
    + python3_10.ACCESS_DEREF_OPCODES
    + python3_10.ATTRIBUTES_OPCODES
    + python3_10.ACCESS_SUBSCR_OPCODES
    + IMPORT_NAME_OPCODES
    + JUMP_OPCODES
    + CALL_OPCODES
    + RETURNING_OPCODES
)

MEMORY_USE_OPCODES = (
    LOAD_FAST_OPCODES
    + LOAD_NAME_OPCODES
    + LOAD_GLOBAL_OPCODES
    + LOAD_DEREF_OPCODES
    + python3_10.LOAD_ATTR_OPCODES
    + IMPORT_FROM_OPCODES
    + python3_10.LOAD_METHOD_OPCODES
    + CLOSURE_LOAD_OPCODES
    + python3_10.BINARY_SUBSCR_OPCODES
)
MEMORY_DEF_OPCODES = (
    MODIFY_FAST_OPCODES
    + MODIFY_NAME_OPCODES
    + MODIFY_GLOBAL_OPCODES
    + MODIFY_DEREF_OPCODES
    + python3_10.MODIFY_ATTR_OPCODES
    + IMPORT_NAME_OPCODES  # compensate incorrect stack effect for IMPORT_NAME
    + python3_10.ACCESS_SUBSCR_OPCODES
)


def get_branch_type(opcode: int) -> bool | None:  # noqa: D103
    match opname[opcode]:
        case (
            "POP_JUMP_FORWARD_IF_TRUE"
            | "POP_JUMP_BACKWARD_IF_TRUE"
            | "POP_JUMP_FORWARD_IF_NOT_NONE"
            | "POP_JUMP_BACKWARD_IF_NOT_NONE"
            | "JUMP_IF_TRUE_OR_POP"
        ):
            return True
        case (
            "POP_JUMP_FORWARD_IF_FALSE"
            | "POP_JUMP_BACKWARD_IF_FALSE"
            | "POP_JUMP_FORWARD_IF_NONE"
            | "POP_JUMP_BACKWARD_IF_NONE"
            | "JUMP_IF_FALSE_OR_POP"
            | "FOR_ITER"
        ):
            return False
        case _:
            return None


def stack_effects(  # noqa: D103, C901
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffects:
    match opname[opcode]:
        case (
            "CACHE"
            | "RETURN_GENERATOR"
            | "ASYNC_GEN_WRAP"
            | "JUMP_BACKWARD_NO_INTERRUPT"
            | "MAKE_CELL"
            | "JUMP_BACKWARD"
            | "COPY_FREE_VARS"
            | "RESUME"
            | "KW_NAMES"
        ):
            return StackEffects(0, 0)
        case "PUSH_NULL" | "MATCH_KEYS" | "BEFORE_WITH" | "COPY":
            return StackEffects(0, 1)
        case (
            "PREP_RERAISE_STAR"
            | "POP_EXCEPT"
            | "POP_JUMP_FORWARD_IF_FALSE"
            | "POP_JUMP_FORWARD_IF_TRUE"
            | "POP_JUMP_FORWARD_IF_NOT_NONE"
            | "POP_JUMP_FORWARD_IF_NONE"
            | "POP_JUMP_BACKWARD_IF_NOT_NONE"
            | "POP_JUMP_BACKWARD_IF_NONE"
            | "POP_JUMP_BACKWARD_IF_FALSE"
            | "POP_JUMP_BACKWARD_IF_TRUE"
            | "CALL"
        ):
            return StackEffects(1, 0)
        case "CHECK_EXC_MATCH" | "CHECK_EG_MATCH" | "SWAP":
            return StackEffects(1, 1)
        case "PUSH_EXC_INFO":
            return StackEffects(1, 2)
        case "END_ASYNC_FOR":
            return StackEffects(2, 0)
        case "BINARY_OP":
            return StackEffects(2, 1)
        case "RERAISE":
            return StackEffects(1, 0)
        case "MATCH_CLASS":
            return StackEffects(3, 1)
        case "LOAD_GLOBAL":
            assert arg is not None
            return StackEffects(0, 2) if arg % 2 == 1 else StackEffects(0, 1)
        case "SEND":
            return StackEffects(1, 0) if jump else StackEffects(0, 0)
        case "MAKE_FUNCTION":
            assert arg is not None
            # argument contains flags
            pops = 1
            if arg & 0x01 != 0:
                pops += 1
            if arg & 0x02 != 0:
                pops += 1
            if arg & 0x04 != 0:
                pops += 1
            if arg & 0x08 != 0:
                pops += 1
            return StackEffects(pops, 1)
        case "CALL_FUNCTION_EX":
            assert arg is not None
            # argument contains flags
            pops = 3
            if arg & 0x01 != 0:
                pops += 1
            return StackEffects(pops, 1)
        case "PRECALL":
            assert arg is not None
            return StackEffects(arg, 0)
        case _:
            return python3_10.stack_effects(
                opcode,
                arg,
                jump=jump,
            )


class Python311InstrumentationInstructionsGenerator(InstrumentationInstructionsGenerator):
    """Generates instrumentation instructions for Python 3.11."""

    @classmethod
    def generate_setup_instructions(
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
                    cf.ArtificialInstr("BINARY_OP", BinaryOp.ADD.value, lineno=lineno),
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
    def generate_method_call_instructions(
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
    def generate_teardown_instructions(
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


class BranchCoverageInstrumentation(python3_10.BranchCoverageInstrumentation):
    """Specialized instrumentation adapter for branch coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    def visit_node(  # noqa: D102
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        maybe_jump_index = JUMP_OP_POS
        maybe_jump = node.try_get_instruction(maybe_jump_index)

        if maybe_jump is None:
            return

        if maybe_jump.opcode == opmap["FOR_ITER"]:
            self.visit_for_loop(
                cfg,
                code_object_id,
                node,
                maybe_jump,
                maybe_jump_index,
            )
            return

        if not maybe_jump.is_cond_jump():
            return

        maybe_compare_index, maybe_compare = node.find_instruction_by_original_index(
            COMPARE_OP_POS,
        )

        if maybe_compare.opcode in python3_10.COMPARE_OPCODES:
            self.visit_compare_based_conditional_jump(
                cfg,
                code_object_id,
                node,
                maybe_compare,
                maybe_compare_index,
            )
            return

        if maybe_compare.opcode == opmap["CHECK_EXC_MATCH"]:
            self.visit_exception_based_conditional_jump(
                cfg,
                code_object_id,
                node,
                maybe_compare,
                maybe_compare_index,
            )
            return

        self.visit_bool_based_conditional_jump(
            cfg,
            code_object_id,
            node,
            maybe_jump,
            maybe_jump_index,
        )


class LineCoverageInstrumentation(python3_10.LineCoverageInstrumentation):
    """Specialized instrumentation adapter for line coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return instr.lineno != lineno and instr.opcode != opmap["RESUME"]


class CheckedCoverageInstrumentation(python3_10.CheckedCoverageInstrumentation):
    """Specialized instrumentation adapter for checked coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return instr.lineno != lineno and instr.opcode != opmap["RESUME"]

    def visit_call(  # noqa: D102, PLR0917
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        # Trace argument only for calls with integer arguments
        argument = instr.arg if isinstance(instr.arg, int) and instr.arg != UNSET else None

        # We want to place the instrumentation instructions before the PRECALL and KW_NAMES
        # instructions, if they are present, otherwise it may cause issues.
        if node.get_instruction(instr_index - 1).opcode == opmap["PRECALL"]:
            instr_index -= 1

        if node.get_instruction(instr_index - 1).opcode == opmap["KW_NAMES"]:
            instr_index -= 1

        # Instrumentation before the original instruction
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_call.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=argument),
                ),
            ),
            instr.lineno,
        )

    METHODS: ClassVar[
        dict[
            tuple[int, ...],
            CheckedCoverageInstrumentationVisitorMethod,
        ]
    ] = {
        OPERATION_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_generic,
        python3_10.ACCESS_FAST_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_local_access,  # noqa: E501
        python3_10.ATTRIBUTES_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_attr_access,
        python3_10.ACCESS_SUBSCR_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_subscr_access,  # noqa: E501
        python3_10.ACCESS_NAME_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_name_access,
        IMPORT_NAME_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_import_name_access,
        python3_10.ACCESS_GLOBAL_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_global_access,  # noqa: E501
        python3_10.ACCESS_DEREF_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_deref_access,  # noqa: E501
        JUMP_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_jump,
        CALL_OPCODES: visit_call,
        RETURNING_OPCODES: python3_10.CheckedCoverageInstrumentation.visit_return,
    }


class DynamicSeedingInstrumentation(python3_10.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    STRING_FUNC_POS = -4

    STRING_FUNC_POS_WITH_ARG = -5
