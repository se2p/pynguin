#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.12."""

from __future__ import annotations

from itertools import chain
from opcode import opname
from typing import TYPE_CHECKING, ClassVar

from bytecode.instr import _UNSET, Instr

from pynguin.instrumentation import PynguinCompare, StackEffects, tracer, transformer
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation.version import python3_10, python3_11
from pynguin.instrumentation.version.common import (
    CheckedCoverageInstrumentationVisitorMethod,
    InstrumentationArgument,
    InstrumentationClassDeref,
    InstrumentationConstantLoad,
    InstrumentationDeref,
    InstrumentationFastLoad,
    InstrumentationMethodCall,
    InstrumentationSetupAction,
    InstrumentationStackValue,
    after,
    before,
    extract_name,
    override,
)
from pynguin.instrumentation.version.python3_11 import (
    CALL_NAMES,
    CLOSURE_LOAD_NAMES,
    IMPORT_FROM_NAMES,
    IMPORT_NAME_NAMES,
    LOAD_GLOBAL_NAMES,
    LOAD_NAME_NAMES,
    MODIFY_DEREF_NAMES,
    MODIFY_FAST_NAMES,
    MODIFY_GLOBAL_NAMES,
    MODIFY_NAME_NAMES,
    STORE_NAME_NAMES,
    YIELDING_NAMES,
    is_conditional_jump,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


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

# Fast opcodes
LOAD_FAST_NAMES = (
    "LOAD_FAST",
    "LOAD_FAST_CHECK",
    "LOAD_FAST_AND_CLEAR",
)
ACCESS_FAST_NAMES = LOAD_FAST_NAMES + python3_11.MODIFY_FAST_NAMES

# Deref opcodes
LOAD_DEREF_NAMES = (
    "LOAD_DEREF",
    "LOAD_FROM_DICT_OR_DEREF",
)
ACCESS_DEREF_NAMES = LOAD_DEREF_NAMES + python3_11.MODIFY_DEREF_NAMES

# Attr opcodes
LOAD_ATTR_NAMES = ("LOAD_ATTR", "LOAD_SUPER_ATTR")
ACCESS_ATTR_NAMES = LOAD_ATTR_NAMES + python3_10.MODIFY_ATTR_NAMES

# Slice opcodes
STORE_SLICE_NAMES = ("STORE_SLICE",)
BINARY_SLICE_NAMES = ("BINARY_SLICE",)
ACCESS_SLICE_NAMES = STORE_SLICE_NAMES + BINARY_SLICE_NAMES

# Remaining opcodes
RETURNING_NAMES = (
    "RETURN_VALUE",
    "RETURN_CONST",
    "YIELD_VALUE",
)

COND_BRANCH_NAMES = (
    "POP_JUMP_IF_NOT_NONE",
    "POP_JUMP_IF_NONE",
    "POP_JUMP_IF_TRUE",
    "POP_JUMP_IF_FALSE",
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
STORE_NAMES = python3_10.STORE_SUBSCR_NAMES + BINARY_SLICE_NAMES + python3_10.STORE_ATTR_NAMES

ACCESS_NAMES = python3_11.IMPORT_FROM_NAMES + LOAD_ATTR_NAMES + python3_10.DELETE_ATTR_NAMES

ATTRIBUTES_NAMES = python3_11.IMPORT_FROM_NAMES + ACCESS_ATTR_NAMES

TRACED_NAMES = (
    python3_11.OPERATION_NAMES
    + ACCESS_FAST_NAMES
    + python3_10.ACCESS_NAME_NAMES
    + python3_10.ACCESS_GLOBAL_NAMES
    + ACCESS_DEREF_NAMES
    + python3_10.ATTRIBUTES_NAMES
    + python3_10.ACCESS_SUBSCR_NAMES
    + ACCESS_SLICE_NAMES
    + python3_11.IMPORT_NAME_NAMES
    + JUMP_NAMES
    + python3_11.CALL_NAMES
    + RETURNING_NAMES
)

MEMORY_USE_NAMES = (
    LOAD_FAST_NAMES
    + python3_11.LOAD_NAME_NAMES
    + python3_11.LOAD_GLOBAL_NAMES
    + LOAD_DEREF_NAMES
    + LOAD_ATTR_NAMES
    + python3_11.IMPORT_FROM_NAMES
    + python3_11.CLOSURE_LOAD_NAMES
    + python3_10.BINARY_SUBSCR_NAMES
    + BINARY_SLICE_NAMES
)
MEMORY_DEF_NAMES = (
    python3_11.MODIFY_FAST_NAMES
    + python3_11.MODIFY_NAME_NAMES
    + python3_11.MODIFY_GLOBAL_NAMES
    + python3_11.MODIFY_DEREF_NAMES
    + python3_10.MODIFY_ATTR_NAMES
    + python3_11.IMPORT_NAME_NAMES  # compensate incorrect stack effect for IMPORT_NAME
    + ACCESS_SLICE_NAMES
)

if TYPE_CHECKING:
    from bytecode import Bytecode
    from bytecode.cfg import BasicBlock


RETURN_NONE_SIZE = 1


def add_for_loop_no_yield_nodes(bytecode: Bytecode) -> Bytecode:  # noqa: D103
    # Starting with Python 3.12, a END_FOR instruction is already placed where we want.
    return bytecode.copy()


def get_branch_type(opcode: int) -> bool | None:  # noqa: D103
    match opname[opcode]:
        case "POP_JUMP_IF_TRUE" | "POP_JUMP_IF_NOT_NONE":
            return True
        case "POP_JUMP_IF_FALSE" | "POP_JUMP_IF_NONE" | "FOR_ITER":
            return False
        case _:
            return None


def end_with_explicit_return_none(instructions: Sequence[Instr]) -> bool:  # noqa: D103
    return (
        len(instructions) >= 2
        # check if the "return None" is implicit or explicit
        and instructions[-2].lineno != instructions[-1].lineno
        and instructions[-1].name == "RETURN_CONST"
        and instructions[-1].arg is None
    )


def stack_effects(  # noqa: D103, C901
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffects:
    match opname[opcode]:
        case (
            "RESERVED"
            | "RETURN_CONST"
            | "CALL_INTRINSIC_1"
            | "INSTRUMENTED_POP_JUMP_IF_NONE"
            | "INSTRUMENTED_POP_JUMP_IF_NOT_NONE"
            | "INSTRUMENTED_RESUME"
            | "INSTRUMENTED_CALL"
            | "INSTRUMENTED_CALL_FUNCTION_EX"
            | "INSTRUMENTED_JUMP_FORWARD"
            | "INSTRUMENTED_JUMP_BACKWARD"
            | "INSTRUMENTED_RETURN_CONST"
            | "INSTRUMENTED_FOR_ITER"
            | "INSTRUMENTED_POP_JUMP_IF_FALSE"
            | "INSTRUMENTED_POP_JUMP_IF_TRUE"
            | "INSTRUMENTED_INSTRUCTION"
            | "JUMP"
            | "JUMP_NO_INTERRUPT"
        ):
            return StackEffects(0, 0)
        case "LOAD_FROM_DICT_OR_GLOBALS" | "LOAD_FROM_DICT_OR_DEREF" | "INSTRUMENTED_YIELD_VALUE":
            return StackEffects(1, 1)
        case "SEND":
            return StackEffects(2, 2)
        case (
            "INTERPRETER_EXIT"
            | "CLEANUP_THROW"
            | "POP_JUMP_IF_NOT_NONE"
            | "POP_JUMP_IF_NONE"
            | "INSTRUMENTED_RETURN_VALUE"
            | "LOAD_SUPER_METHOD"
            | "LOAD_ZERO_SUPER_METHOD"
            | "LOAD_ZERO_SUPER_ATTR"
            | "STORE_FAST_MAYBE_NULL"
            | "INSTRUMENTED_END_SEND"
        ):
            return StackEffects(1, 0)
        case "END_FOR" | "INSTRUMENTED_END_FOR":
            return StackEffects(2, 0)
        case "SETUP_CLEANUP":
            return StackEffects(0, 2)
        case "END_SEND" | "CALL_INTRINSIC_2":
            return StackEffects(2, 1)
        case "FOR_ITER":
            return StackEffects(1, 2)
        case "BINARY_SLICE":
            return StackEffects(3, 1)
        case "STORE_SLICE":
            return StackEffects(4, 0)
        case "LOAD_LOCALS" | "LOAD_FAST_CHECK" | "LOAD_FAST_AND_CLEAR" | "SETUP_FINALLY":
            return StackEffects(0, 1)
        case "LOAD_ATTR":
            assert arg is not None
            return StackEffects(1, 2) if arg & 0x01 != 0 else StackEffects(1, 1)
        case "LOAD_SUPER_ATTR" | "INSTRUMENTED_LOAD_SUPER_ATTR":
            assert arg is not None
            return StackEffects(2, 1) if arg & 0x01 != 0 else StackEffects(3, 1)
        case "CALL":
            assert arg is not None
            return StackEffects(2 + arg, 1)
        case _:
            return python3_11.stack_effects(opcode, arg, jump=jump)


class Python312InstrumentationInstructionsGenerator(
    python3_11.Python311InstrumentationInstructionsGenerator
):
    """Generates instrumentation instructions for Python 3.12."""

    @classmethod
    def _generate_argument_instructions(
        cls,
        arg: InstrumentationArgument,
        position: int,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match arg:
            case InstrumentationClassDeref(name):
                return (
                    cf.ArtificialInstr("LOAD_LOCALS", lineno=lineno),
                    cf.ArtificialInstr("LOAD_FROM_DICT_OR_DEREF", name, lineno=lineno),
                )
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
            cf.ArtificialInstr("LOAD_ATTR", (True, method_call.method_name), lineno=lineno),
            *chain(
                *(
                    cls._generate_argument_instructions(arg, position, lineno)
                    for position, arg in enumerate(method_call.args)
                )
            ),
            cf.ArtificialInstr("CALL", len(method_call.args), lineno=lineno),
        )


class BranchCoverageInstrumentation(python3_11.BranchCoverageInstrumentation):
    """Specialized instrumentation adapter for branch coverage in Python 3.12."""

    instructions_generator = Python312InstrumentationInstructionsGenerator

    NONE_BASED_JUMPS_MAPPING: ClassVar[dict[str, PynguinCompare]] = {
        "POP_JUMP_IF_NOT_NONE": PynguinCompare.IS_NOT,
        "POP_JUMP_IF_NONE": PynguinCompare.IS,
    }

    def visit_for_loop_natural_exit(  # noqa: D102
        self,
        for_loop_natural_exit: BasicBlock,
        predicate_id: int,
        lineno: int | _UNSET | None,
    ) -> None:
        end_for_position = None
        while end_for_position is None:
            for i, instr in enumerate(for_loop_natural_exit):
                if isinstance(instr, Instr) and instr.name == "END_FOR":
                    end_for_position = i
                    break
            else:
                assert for_loop_natural_exit.next_block is not None, (
                    "Expected END_FOR instruction in for_loop_natural_exit, but found none."
                )
                for_loop_natural_exit = for_loop_natural_exit.next_block

        # Insert a call to the tracer after the END_FOR instruction.
        for_loop_natural_exit[after(end_for_position)] = (
            self.instructions_generator.generate_instructions(
                InstrumentationSetupAction.NO_ACTION,
                InstrumentationMethodCall(
                    self._subject_properties.instrumentation_tracer,
                    tracer.InstrumentationExecutionTracer.executed_bool_predicate.__name__,
                    (
                        InstrumentationConstantLoad(value=False),
                        InstrumentationConstantLoad(value=predicate_id),
                    ),
                ),
                lineno,
            )
        )


class LineCoverageInstrumentation(python3_11.LineCoverageInstrumentation):
    """Specialized instrumentation adapter for line coverage in Python 3.12."""

    instructions_generator = Python312InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return super().should_instrument_line(instr, lineno) and instr.name != "END_FOR"


class CheckedCoverageInstrumentation(python3_11.CheckedCoverageInstrumentation):
    """Specialized instrumentation adapter for checked coverage in Python 3.12."""

    instructions_generator = Python312InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return super().should_instrument_line(instr, lineno) and instr.name != "END_FOR"

    def visit_local_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        instructions = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=instr.arg),  # type: ignore[arg-type]
                    InstrumentationFastLoad(name=instr.arg),  # type: ignore[arg-type]
                ),
            ),
            instr.lineno,
        )

        match instr.name:
            case "DELETE_FAST" | "LOAD_FAST_AND_CLEAR":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[before(instr_index)] = instructions
            case "LOAD_FAST" | "LOAD_FAST_CHECK" | "STORE_FAST":
                # Instrumentation after the original instruction
                node.basic_block[after(instr_index)] = instructions

    def visit_attr_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        name = extract_name(instr.arg)
        assert name is not None, "Attribute access must have a name."

        method_call = InstrumentationMethodCall(
            self._subject_properties.instrumentation_tracer,
            tracer.InstrumentationExecutionTracer.track_attribute_access.__name__,
            (
                InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                InstrumentationConstantLoad(value=code_object_id),
                InstrumentationConstantLoad(value=node.index),
                InstrumentationConstantLoad(value=instr.opcode),
                InstrumentationConstantLoad(value=instr.lineno),
                InstrumentationConstantLoad(value=instr_original_index),
                InstrumentationConstantLoad(value=name),
                InstrumentationStackValue.FIRST,
            ),
        )

        match instr.name:
            case "LOAD_ATTR" | "LOAD_SUPER_ATTR" | "DELETE_ATTR" | "IMPORT_FROM":
                # Instrumentation before the original instruction
                node.basic_block[before(instr_index)] = (
                    self.instructions_generator.generate_instructions(
                        InstrumentationSetupAction.COPY_FIRST,
                        method_call,
                        instr.lineno,
                    )
                )
            case "STORE_ATTR":
                # Instrumentation mostly after the original instruction
                node.basic_block[override(instr_index)] = (
                    self.instructions_generator.generate_overriding_instructions(
                        InstrumentationSetupAction.COPY_FIRST_SHIFT_DOWN_TWO,
                        instr,
                        method_call,
                        instr.lineno,
                    )
                )

    def visit_slice_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        method_call = InstrumentationMethodCall(
            self._subject_properties.instrumentation_tracer,
            tracer.InstrumentationExecutionTracer.track_attribute_access.__name__,
            (
                InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                InstrumentationConstantLoad(value=code_object_id),
                InstrumentationConstantLoad(value=node.index),
                InstrumentationConstantLoad(value=instr.opcode),
                InstrumentationConstantLoad(value=instr.lineno),
                InstrumentationConstantLoad(value=instr_original_index),
                InstrumentationConstantLoad(value=None),
                InstrumentationStackValue.FIRST,
            ),
        )

        match instr.name:
            case "STORE_SLICE":
                # Instrumentation mostly after the original instruction
                node.basic_block[override(instr_index)] = (
                    self.instructions_generator.generate_overriding_instructions(
                        InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_FOUR,
                        instr,
                        method_call,
                        instr.lineno,
                    )
                )
            case "BINARY_SLICE":
                # Instrumentation mostly after the original instruction
                node.basic_block[override(instr_index)] = (
                    self.instructions_generator.generate_overriding_instructions(
                        InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_THREE,
                        instr,
                        method_call,
                        instr.lineno,
                    )
                )

    def visit_deref_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        value_instruction = (
            InstrumentationClassDeref(name=instr.arg)  # type: ignore[arg-type]
            if instr.name == "LOAD_FROM_DICT_OR_DEREF"
            else InstrumentationDeref(name=instr.arg)  # type: ignore[arg-type]
        )

        instructions = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=instr.arg),  # type: ignore[arg-type]
                    value_instruction,
                ),
            ),
            instr.lineno,
        )

        match instr.name:
            case "DELETE_DEREF":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[before(instr_index)] = instructions
            case "STORE_DEREF" | "LOAD_DEREF" | "LOAD_FROM_DICT_OR_DEREF":
                # Instrumentation after the original instruction
                node.basic_block[after(instr_index)] = instructions

    METHODS: ClassVar[
        dict[
            tuple[str, ...],
            CheckedCoverageInstrumentationVisitorMethod,
        ]
    ] = {
        python3_11.OPERATION_NAMES: python3_11.CheckedCoverageInstrumentation.visit_generic,
        ACCESS_FAST_NAMES: visit_local_access,
        ATTRIBUTES_NAMES: visit_attr_access,
        python3_10.ACCESS_SUBSCR_NAMES: python3_11.CheckedCoverageInstrumentation.visit_subscr_access,  # noqa: E501
        ACCESS_SLICE_NAMES: visit_slice_access,
        python3_10.ACCESS_NAME_NAMES: python3_11.CheckedCoverageInstrumentation.visit_name_access,
        IMPORT_NAME_NAMES: python3_11.CheckedCoverageInstrumentation.visit_import_name_access,
        python3_10.ACCESS_GLOBAL_NAMES: python3_11.CheckedCoverageInstrumentation.visit_global_access,  # noqa: E501
        ACCESS_DEREF_NAMES: visit_deref_access,
        JUMP_NAMES: python3_11.CheckedCoverageInstrumentation.visit_jump,
        CALL_NAMES: python3_11.CheckedCoverageInstrumentation.visit_call,
        RETURNING_NAMES: python3_11.CheckedCoverageInstrumentation.visit_return,
    }


class DynamicSeedingInstrumentation(python3_11.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.12."""

    instructions_generator = Python312InstrumentationInstructionsGenerator

    STRING_FUNC_POS = -3

    STRING_FUNC_POS_WITH_ARG = -4

    def extract_method_name(self, instr: Instr) -> str | None:  # noqa: D102
        return extract_name(instr.arg) if instr.name == "LOAD_ATTR" else None
