#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.13."""

from opcode import opname
from typing import ClassVar

from bytecode.cfg import BasicBlock
from bytecode.instr import _UNSET, UNSET, Compare, Instr

from pynguin.instrumentation import PynguinCompare, StackEffects, tracer, transformer
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation.controlflow import CFG, ArtificialInstr, BasicBlockNode
from pynguin.instrumentation.version import python3_10, python3_11, python3_12
from pynguin.instrumentation.version.common import (
    CheckedCoverageInstrumentationVisitorMethod,
    ExtractComparisonFunction,
    InstrumentationArgument,
    InstrumentationConstantLoad,
    InstrumentationFastLoadTuple,
    InstrumentationMethodCall,
    InstrumentationSetupAction,
    after,
    before,
)
from pynguin.instrumentation.version.python3_12 import (
    ACCESS_NAMES,
    CLOSURE_LOAD_NAMES,
    COND_BRANCH_NAMES,
    IMPORT_FROM_NAMES,
    IMPORT_NAME_NAMES,
    LOAD_DEREF_NAMES,
    LOAD_GLOBAL_NAMES,
    LOAD_NAME_NAMES,
    MODIFY_DEREF_NAMES,
    MODIFY_GLOBAL_NAMES,
    MODIFY_NAME_NAMES,
    RETURN_NONE_SIZE,
    RETURNING_NAMES,
    STORE_NAME_NAMES,
    STORE_NAMES,
    YIELDING_NAMES,
    add_for_loop_no_yield_nodes,
    end_with_explicit_return_none,
    get_branch_type,
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

# Fast opcodes
LOAD_FAST_NAMES = (
    *python3_12.LOAD_FAST_NAMES,
    "LOAD_FAST_LOAD_FAST",
    "STORE_FAST_LOAD_FAST",
)
MODIFY_FAST_NAMES = (
    *python3_12.MODIFY_FAST_NAMES,
    "STORE_FAST_STORE_FAST",
    "STORE_FAST_LOAD_FAST",
)
ACCESS_FAST_NAMES = (
    *python3_12.LOAD_FAST_NAMES,
    "LOAD_FAST_LOAD_FAST",
    *python3_12.MODIFY_FAST_NAMES,
    "STORE_FAST_STORE_FAST",
    "STORE_FAST_LOAD_FAST",
)

# Remaining opcodes
CALL_NAMES = (
    *python3_12.CALL_NAMES,
    "CALL_KW",
)

OPERATION_NAMES = (
    *python3_10.COMPARE_NAMES,
    # Unary operations
    "UNARY_NEGATIVE",
    "UNARY_NOT",
    "UNARY_INVERT",
    "GET_ITER",
    "GET_YIELD_FROM_ITER",
    "TO_BOOL",
    # Binary and in-place operations
    "BINARY_OP",
)

# Regrouping opcodes
TRACED_NAMES = (
    python3_11.OPERATION_NAMES
    + ACCESS_FAST_NAMES
    + python3_10.ACCESS_NAME_NAMES
    + python3_10.ACCESS_GLOBAL_NAMES
    + python3_12.ACCESS_DEREF_NAMES
    + python3_12.ATTRIBUTES_NAMES
    + python3_10.ACCESS_SUBSCR_NAMES
    + python3_12.ACCESS_SLICE_NAMES
    + python3_12.IMPORT_NAME_NAMES
    + python3_12.JUMP_NAMES
    + CALL_NAMES
    + python3_12.RETURNING_NAMES
)

MEMORY_USE_NAMES = (
    LOAD_FAST_NAMES
    + python3_12.LOAD_NAME_NAMES
    + python3_12.LOAD_GLOBAL_NAMES
    + python3_12.LOAD_DEREF_NAMES
    + python3_12.LOAD_ATTR_NAMES
    + python3_12.IMPORT_FROM_NAMES
    + python3_10.LOAD_METHOD_NAMES
    + python3_12.CLOSURE_LOAD_NAMES
    + python3_10.BINARY_SUBSCR_NAMES
    + python3_12.BINARY_SLICE_NAMES
)
MEMORY_DEF_NAMES = (
    MODIFY_FAST_NAMES
    + python3_12.MODIFY_NAME_NAMES
    + python3_12.MODIFY_GLOBAL_NAMES
    + python3_12.MODIFY_DEREF_NAMES
    + python3_10.MODIFY_ATTR_NAMES
    + python3_12.IMPORT_NAME_NAMES  # compensate incorrect stack effect for IMPORT_NAME
    + python3_10.ACCESS_SUBSCR_NAMES
    + python3_12.ACCESS_SLICE_NAMES
)


def stack_effects(  # noqa: D103, C901
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffects:
    match opname[opcode]:
        case "ENTER_EXECUTOR" | "INSTRUMENTED_CALL_KW":
            return StackEffects(0, 0)
        case "END_FOR" | "INSTRUMENTED_END_FOR" | "EXIT_INIT_CHECK":
            return StackEffects(1, 0)
        case (
            "FORMAT_SIMPLE" | "TO_BOOL" | "CONVERT_VALUE" | "STORE_FAST_LOAD_FAST" | "MAKE_FUNCTION"
        ):
            return StackEffects(1, 1)
        case "RETURN_GENERATOR":
            return StackEffects(0, 1)
        case "FORMAT_WITH_SPEC" | "SET_FUNCTION_ATTRIBUTE":
            return StackEffects(2, 1)
        case "STORE_FAST_STORE_FAST":
            return StackEffects(2, 0)
        case "LOAD_FAST_LOAD_FAST":
            return StackEffects(0, 2)
        case "SETUP_WITH":
            return StackEffects(0, 1) if jump else StackEffects(0, 0)
        case "SETUP_CLEANUP":
            return StackEffects(0, 2) if jump else StackEffects(0, 0)
        case "SETUP_FINALLY":
            return StackEffects(0, 1) if jump else StackEffects(0, 0)
        case "CALL_KW":
            assert arg is not None
            return StackEffects(3 + arg, 1)
        case _:
            return python3_12.stack_effects(opcode, arg, jump=jump)


def extract_comparison(instr: Instr) -> PynguinCompare:
    """Extract the comparison from an instruction.

    Args:
        instr: The instruction from which to extract the comparison.

    Returns:
        The extracted comparison.
    """
    match instr.name:
        case "COMPARE_OP":
            match instr.arg:
                case Compare.LT | Compare.LT_CAST:
                    return PynguinCompare.LT
                case Compare.LE | Compare.LE_CAST:
                    return PynguinCompare.LE
                case Compare.EQ | Compare.EQ_CAST:
                    return PynguinCompare.EQ
                case Compare.NE | Compare.NE_CAST:
                    return PynguinCompare.NE
                case Compare.GT | Compare.GT_CAST:
                    return PynguinCompare.GT
                case Compare.GE | Compare.GE_CAST:
                    return PynguinCompare.GE
                case _:
                    raise AssertionError(f"Unknown comparison op in {instr}.")
        case _:
            return python3_10.extract_comparison(instr)


class Python313InstrumentationInstructionsGenerator(
    python3_12.Python312InstrumentationInstructionsGenerator
):
    """Generates instrumentation instructions for Python 3.13."""

    @classmethod
    def _generate_argument_instructions(
        cls,
        arg: InstrumentationArgument,
        position: int,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match arg:
            case InstrumentationFastLoadTuple(names):
                return (
                    cf.ArtificialInstr("LOAD_FAST_LOAD_FAST", arg=names, lineno=lineno),
                    cf.ArtificialInstr("BUILD_TUPLE", 2, lineno=lineno),
                )
            case _:
                return super()._generate_argument_instructions(arg, position, lineno)


class BranchCoverageInstrumentation(python3_12.BranchCoverageInstrumentation):
    """Specialized instrumentation adapter for branch coverage in Python 3.13."""

    instructions_generator = Python313InstrumentationInstructionsGenerator

    extract_comparison: ExtractComparisonFunction = staticmethod(extract_comparison)

    def visit_for_loop_natural_exit(  # noqa: D102
        self,
        for_loop_natural_exit: BasicBlock,
        predicate_id: int,
        lineno: int | _UNSET | None,
    ) -> None:
        pop_top_position = None
        while pop_top_position is None:
            for i, instr in enumerate(for_loop_natural_exit):
                if isinstance(instr, Instr) and instr.name == "POP_TOP":
                    pop_top_position = i
                    break
            else:
                assert for_loop_natural_exit.next_block is not None, (
                    "Expected POP_TOP instruction in for_loop_natural_exit, but found none."
                )
                for_loop_natural_exit = for_loop_natural_exit.next_block

        # Insert a call to the tracer after the POP_TOP instruction.
        for_loop_natural_exit[after(pop_top_position)] = (
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


class LineCoverageInstrumentation(python3_12.LineCoverageInstrumentation):
    """Specialized instrumentation adapter for line coverage in Python 3.13."""

    instructions_generator = Python313InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return super().should_instrument_line(instr, lineno) and instr.name != "POP_TOP"


class CheckedCoverageInstrumentation(python3_12.CheckedCoverageInstrumentation):
    """Specialized instrumentation adapter for checked coverage in Python 3.13."""

    instructions_generator = Python313InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return super().should_instrument_line(instr, lineno) and instr.name != "POP_TOP"

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
        if instr.name in python3_12.ACCESS_FAST_NAMES:
            super().visit_local_access(
                ast_info,
                cfg,
                code_object_id,
                node,
                instr,
                instr_index,
                instr_original_index,
            )
            return

        node.basic_block[after(instr_index)] = self.generate_instructions(
            cfg, code_object_id, instr, instr_original_index, node
        )

    def generate_instructions(
        self,
        cfg: CFG,
        code_object_id: int,
        instr: Instr,
        instr_original_index: int,
        node: BasicBlockNode,
    ) -> tuple[ArtificialInstr, ...]:
        """Generate instrumentation instructions.

        Args:
            cfg: The CFG.
            code_object_id: The ID of the code object.
            instr: The instruction to instrument.
            instr_original_index: The original index of the instruction.
            node: The node that contains the instruction.
        """
        return self.instructions_generator.generate_instructions(
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
                    InstrumentationFastLoadTuple(names=instr.arg),  # type: ignore[arg-type]
                ),
            ),
            instr.lineno,
        )

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
        OPERATION_NAMES: python3_12.CheckedCoverageInstrumentation.visit_generic,
        ACCESS_FAST_NAMES: visit_local_access,
        python3_12.ATTRIBUTES_NAMES: python3_12.CheckedCoverageInstrumentation.visit_attr_access,
        python3_10.ACCESS_SUBSCR_NAMES: python3_12.CheckedCoverageInstrumentation.visit_subscr_access,  # noqa: E501
        python3_12.ACCESS_SLICE_NAMES: python3_12.CheckedCoverageInstrumentation.visit_slice_access,
        python3_10.ACCESS_NAME_NAMES: python3_12.CheckedCoverageInstrumentation.visit_name_access,
        python3_12.IMPORT_NAME_NAMES: python3_12.CheckedCoverageInstrumentation.visit_import_name_access,  # noqa: E501
        python3_10.ACCESS_GLOBAL_NAMES: python3_12.CheckedCoverageInstrumentation.visit_global_access,  # noqa: E501
        python3_12.ACCESS_DEREF_NAMES: python3_12.CheckedCoverageInstrumentation.visit_deref_access,
        python3_12.JUMP_NAMES: python3_12.CheckedCoverageInstrumentation.visit_jump,
        CALL_NAMES: visit_call,
        python3_12.RETURNING_NAMES: python3_12.CheckedCoverageInstrumentation.visit_return,
    }


class DynamicSeedingInstrumentation(python3_12.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.13."""

    instructions_generator = Python313InstrumentationInstructionsGenerator

    STRING_FUNC_POS = -4

    STRING_FUNC_POS_WITH_ARG = -5
