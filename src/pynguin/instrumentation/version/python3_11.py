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

from itertools import chain
from opcode import opname
from typing import ClassVar

from bytecode.instr import _UNSET, UNSET, BinaryOp, Instr

from pynguin.instrumentation import PynguinCompare, StackEffects, tracer, transformer
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation.version import python3_10
from pynguin.instrumentation.version.common import (
    COMPARE_OP_POS,
    JUMP_OP_POS,
    CheckedCoverageInstrumentationVisitorMethod,
    InstrumentationArgument,
    InstrumentationConstantLoad,
    InstrumentationGlobalLoad,
    InstrumentationMethodCall,
    InstrumentationSetupAction,
    InstrumentationStackValue,
    before,
)
from pynguin.instrumentation.version.python3_10 import (
    ACCESS_NAMES,
    CLOSURE_LOAD_NAMES,
    IMPORT_FROM_NAMES,
    IMPORT_NAME_NAMES,
    LOAD_DEREF_NAMES,
    LOAD_FAST_NAMES,
    LOAD_GLOBAL_NAMES,
    LOAD_NAME_NAMES,
    MODIFY_DEREF_NAMES,
    MODIFY_FAST_NAMES,
    MODIFY_GLOBAL_NAMES,
    MODIFY_NAME_NAMES,
    RETURN_NONE_SIZE,
    RETURNING_NAMES,
    STORE_NAME_NAMES,
    STORE_NAMES,
    add_for_loop_no_yield_nodes,
    end_with_explicit_return_none,
    is_conditional_jump,
)

__all__ = [
    "ACCESS_NAMES",
    "CALL_NAMES",
    "CLOSURE_LOAD_NAMES",
    "COND_BRANCH_NAMES",
    "IMPORT_FROM_NAMES",
    "IMPORT_NAME_NAMES",
    "LOAD_DEREF_NAMES",
    "LOAD_FAST_NAMES",
    "LOAD_GLOBAL_NAMES",
    "LOAD_NAME_NAMES",
    "MEMORY_DEF_NAMES",
    "MEMORY_USE_NAMES",
    "MODIFY_DEREF_NAMES",
    "MODIFY_FAST_NAMES",
    "MODIFY_GLOBAL_NAMES",
    "MODIFY_NAME_NAMES",
    "RETURNING_NAMES",
    "RETURN_NONE_SIZE",
    "STORE_NAMES",
    "STORE_NAME_NAMES",
    "TRACED_NAMES",
    "YIELDING_NAMES",
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
CALL_NAMES = (
    "CALL",
    "CALL_FUNCTION_EX",
)

YIELDING_NAMES = ("YIELD_VALUE",)

OPERATION_NAMES = (
    *python3_10.COMPARE_NAMES,
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

COND_BRANCH_NAMES = (
    "POP_JUMP_FORWARD_IF_NOT_NONE",
    "POP_JUMP_BACKWARD_IF_NOT_NONE",
    "POP_JUMP_FORWARD_IF_NONE",
    "POP_JUMP_BACKWARD_IF_NONE",
    "POP_JUMP_FORWARD_IF_TRUE",
    "POP_JUMP_BACKWARD_IF_TRUE",
    "JUMP_IF_TRUE_OR_POP",
    "POP_JUMP_FORWARD_IF_FALSE",
    "POP_JUMP_BACKWARD_IF_FALSE",
    "JUMP_IF_FALSE_OR_POP",
    "FOR_ITER",
)

JUMP_NAMES = (
    *COND_BRANCH_NAMES,
    "JUMP_FORWARD",
    "JUMP_BACKWARD",
    "JUMP_BACKWARD_NO_INTERRUPT",
    "BEFORE_WITH",
    "BEFORE_ASYNC_WITH",
)


# Regrouping opcodes
TRACED_NAMES = (
    OPERATION_NAMES
    + python3_10.ACCESS_FAST_NAMES
    + python3_10.ACCESS_NAME_NAMES
    + python3_10.ACCESS_GLOBAL_NAMES
    + python3_10.ACCESS_DEREF_NAMES
    + python3_10.ATTRIBUTES_NAMES
    + python3_10.ACCESS_SUBSCR_NAMES
    + IMPORT_NAME_NAMES
    + JUMP_NAMES
    + CALL_NAMES
    + RETURNING_NAMES
)

MEMORY_USE_NAMES = (
    LOAD_FAST_NAMES
    + LOAD_NAME_NAMES
    + LOAD_GLOBAL_NAMES
    + LOAD_DEREF_NAMES
    + python3_10.LOAD_ATTR_NAMES
    + IMPORT_FROM_NAMES
    + python3_10.LOAD_METHOD_NAMES
    + CLOSURE_LOAD_NAMES
    + python3_10.BINARY_SUBSCR_NAMES
)
MEMORY_DEF_NAMES = (
    MODIFY_FAST_NAMES
    + MODIFY_NAME_NAMES
    + MODIFY_GLOBAL_NAMES
    + MODIFY_DEREF_NAMES
    + python3_10.MODIFY_ATTR_NAMES
    + IMPORT_NAME_NAMES  # compensate incorrect stack effect for IMPORT_NAME
    + python3_10.ACCESS_SUBSCR_NAMES
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
        ):
            return StackEffects(1, 0)
        case "CHECK_EXC_MATCH" | "CHECK_EG_MATCH" | "SWAP":
            return StackEffects(1, 1)
        case "PUSH_EXC_INFO":
            return StackEffects(1, 2)
        case "END_ASYNC_FOR":
            return StackEffects(2, 0)
        case "BINARY_OP" | "CALL":
            return StackEffects(2, 1)
        case "RERAISE":
            return StackEffects(1, 0)
        case "MATCH_CLASS":
            return StackEffects(3, 1)
        case "LOAD_GLOBAL":
            assert arg is not None
            return StackEffects(0, 2) if arg & 0x01 != 0 else StackEffects(0, 1)
        case "SEND":
            return StackEffects(2, 1) if jump else StackEffects(2, 2)
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
            return StackEffects(2 + arg, 2)
        case _:
            return python3_10.stack_effects(
                opcode,
                arg,
                jump=jump,
            )


class Python311InstrumentationInstructionsGenerator(
    python3_10.Python310InstrumentationInstructionsGenerator
):
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
            case InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_THREE:
                return (
                    cf.ArtificialInstr("COPY", 3, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 3, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 2, lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_FOUR:
                return (
                    cf.ArtificialInstr("COPY", 3, lineno=lineno),
                    cf.ArtificialInstr("SWAP", 5, lineno=lineno),
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
    def _generate_argument_instructions(
        cls,
        arg: InstrumentationArgument,
        position: int,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match arg:
            case InstrumentationGlobalLoad(name):
                return (cf.ArtificialInstr("LOAD_GLOBAL", arg=(False, name), lineno=lineno),)
            case InstrumentationStackValue():
                return (cf.ArtificialInstr("COPY", position + 2 + arg.value, lineno=lineno),)
            case _:
                return super()._generate_argument_instructions(arg, position, lineno)

    @classmethod
    def generate_method_call_instructions(
        cls,
        method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        return (
            cf.ArtificialInstr("LOAD_CONST", method_call.self, lineno=lineno),
            cf.ArtificialInstr("LOAD_METHOD", method_call.method_name, lineno=lineno),
            *chain(
                *(
                    cls._generate_argument_instructions(arg, position, lineno)
                    for position, arg in enumerate(method_call.args)
                )
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
                | InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_THREE
                | InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_FOUR
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

    NONE_BASED_JUMPS_MAPPING: ClassVar[dict[str, PynguinCompare]] = {
        "POP_JUMP_FORWARD_IF_NOT_NONE": PynguinCompare.IS_NOT,
        "POP_JUMP_BACKWARD_IF_NOT_NONE": PynguinCompare.IS_NOT,
        "POP_JUMP_FORWARD_IF_NONE": PynguinCompare.IS,
        "POP_JUMP_BACKWARD_IF_NONE": PynguinCompare.IS,
    }

    def visit_node(  # noqa: D102
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        maybe_jump_index = JUMP_OP_POS
        maybe_jump = node.try_get_instruction(maybe_jump_index)

        if maybe_jump is None:
            return

        if (
            ast_info is not None
            and isinstance(maybe_jump.lineno, int)
            and not ast_info.should_cover_conditional_statement(maybe_jump.lineno)
        ):
            return

        if maybe_jump.name == "FOR_ITER":
            self.visit_for_loop(
                ast_info,
                cfg,
                code_object_id,
                node,
                maybe_jump,
                maybe_jump_index,
            )
            return

        if maybe_jump.name in self.NONE_BASED_JUMPS_MAPPING:
            self.visit_none_based_conditional_jump(
                ast_info,
                cfg,
                code_object_id,
                node,
                maybe_jump,
                maybe_jump_index,
            )
            return

        if not maybe_jump.is_cond_jump():
            return

        try:
            maybe_compare_index, maybe_compare = node.find_instruction_by_original_index(
                COMPARE_OP_POS,
            )
        except IndexError:
            pass
        else:
            if maybe_compare.name in python3_10.COMPARE_NAMES:
                self.visit_compare_based_conditional_jump(
                    ast_info,
                    cfg,
                    code_object_id,
                    node,
                    maybe_compare,
                    maybe_compare_index,
                )
                return

            if maybe_compare.name == "CHECK_EXC_MATCH":
                self.visit_exception_based_conditional_jump(
                    ast_info,
                    cfg,
                    code_object_id,
                    node,
                    maybe_compare,
                    maybe_compare_index,
                )
                return

        self.visit_bool_based_conditional_jump(
            ast_info,
            cfg,
            code_object_id,
            node,
            maybe_jump,
            maybe_jump_index,
        )

    def visit_none_based_conditional_jump(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=instr.lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.COPY_FIRST,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.executed_compare_predicate.__name__,
                (
                    InstrumentationStackValue.FIRST,
                    InstrumentationConstantLoad(value=None),
                    InstrumentationConstantLoad(value=predicate_id),
                    InstrumentationConstantLoad(value=self.NONE_BASED_JUMPS_MAPPING[instr.name]),
                ),
            ),
            instr.lineno,
        )


class LineCoverageInstrumentation(python3_10.LineCoverageInstrumentation):
    """Specialized instrumentation adapter for line coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return instr.lineno != lineno and instr.name != "RESUME"


class CheckedCoverageInstrumentation(python3_10.CheckedCoverageInstrumentation):
    """Specialized instrumentation adapter for checked coverage in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return super().should_instrument_line(instr, lineno) and instr.name != "RESUME"

    def visit_call(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
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
        precall_instr = node.try_get_instruction(instr_index - 1)
        assert precall_instr is not None, (
            f"A Instruction should exist at index {instr_index - 1} in {node.basic_block}"
        )
        if precall_instr.name == "PRECALL":
            instr_index -= 1

        kw_names_instr = node.try_get_instruction(instr_index - 1)
        assert kw_names_instr is not None, (
            f"Instruction should exist at index {instr_index - 1} in {node.basic_block}"
        )
        if kw_names_instr.name == "KW_NAMES":
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
            tuple[str, ...],
            CheckedCoverageInstrumentationVisitorMethod,
        ]
    ] = {
        OPERATION_NAMES: python3_10.CheckedCoverageInstrumentation.visit_generic,
        python3_10.ACCESS_FAST_NAMES: python3_10.CheckedCoverageInstrumentation.visit_local_access,
        python3_10.ATTRIBUTES_NAMES: python3_10.CheckedCoverageInstrumentation.visit_attr_access,
        python3_10.ACCESS_SUBSCR_NAMES: python3_10.CheckedCoverageInstrumentation.visit_subscr_access,  # noqa: E501
        python3_10.ACCESS_NAME_NAMES: python3_10.CheckedCoverageInstrumentation.visit_name_access,
        IMPORT_NAME_NAMES: python3_10.CheckedCoverageInstrumentation.visit_import_name_access,
        python3_10.ACCESS_GLOBAL_NAMES: python3_10.CheckedCoverageInstrumentation.visit_global_access,  # noqa: E501
        python3_10.ACCESS_DEREF_NAMES: python3_10.CheckedCoverageInstrumentation.visit_deref_access,
        JUMP_NAMES: python3_10.CheckedCoverageInstrumentation.visit_jump,
        CALL_NAMES: visit_call,
        RETURNING_NAMES: python3_10.CheckedCoverageInstrumentation.visit_return,
    }


class DynamicSeedingInstrumentation(python3_10.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.11."""

    instructions_generator = Python311InstrumentationInstructionsGenerator

    STRING_FUNC_POS = -4

    STRING_FUNC_POS_WITH_ARG = -5
