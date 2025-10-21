#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.14."""

from __future__ import annotations

from itertools import chain
from opcode import opname
from typing import ClassVar

from bytecode.instr import _UNSET
from bytecode.instr import UNSET
from bytecode.instr import Instr

from pynguin.instrumentation import StackEffects
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation import tracer
from pynguin.instrumentation import transformer
from pynguin.instrumentation.version import python3_10
from pynguin.instrumentation.version import python3_11
from pynguin.instrumentation.version import python3_12
from pynguin.instrumentation.version import python3_13
from pynguin.instrumentation.version.common import (
    CheckedCoverageInstrumentationVisitorMethod,
)
from pynguin.instrumentation.version.common import InstrumentationArgument
from pynguin.instrumentation.version.common import InstrumentationConstantLoad
from pynguin.instrumentation.version.common import InstrumentationFastLoad
from pynguin.instrumentation.version.common import InstrumentationFastLoadTuple
from pynguin.instrumentation.version.common import InstrumentationMethodCall
from pynguin.instrumentation.version.common import InstrumentationSetupAction
from pynguin.instrumentation.version.common import InstrumentedSmallIntLoad
from pynguin.instrumentation.version.common import after
from pynguin.instrumentation.version.common import before
from pynguin.instrumentation.version.python3_13 import ACCESS_NAMES
from pynguin.instrumentation.version.python3_13 import CLOSURE_LOAD_NAMES
from pynguin.instrumentation.version.python3_13 import COND_BRANCH_NAMES
from pynguin.instrumentation.version.python3_13 import IMPORT_FROM_NAMES
from pynguin.instrumentation.version.python3_13 import IMPORT_NAME_NAMES
from pynguin.instrumentation.version.python3_13 import LOAD_DEREF_NAMES
from pynguin.instrumentation.version.python3_13 import LOAD_GLOBAL_NAMES
from pynguin.instrumentation.version.python3_13 import LOAD_NAME_NAMES
from pynguin.instrumentation.version.python3_13 import MODIFY_DEREF_NAMES
from pynguin.instrumentation.version.python3_13 import MODIFY_GLOBAL_NAMES
from pynguin.instrumentation.version.python3_13 import MODIFY_NAME_NAMES
from pynguin.instrumentation.version.python3_13 import RETURN_NONE_SIZE
from pynguin.instrumentation.version.python3_13 import RETURNING_NAMES
from pynguin.instrumentation.version.python3_13 import STORE_NAME_NAMES
from pynguin.instrumentation.version.python3_13 import STORE_NAMES
from pynguin.instrumentation.version.python3_13 import YIELDING_NAMES
from pynguin.instrumentation.version.python3_13 import add_for_loop_no_yield_nodes
from pynguin.instrumentation.version.python3_13 import end_with_explicit_return_none
from pynguin.instrumentation.version.python3_13 import get_branch_type
from pynguin.instrumentation.version.python3_13 import is_conditional_jump


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
    *python3_13.LOAD_FAST_NAMES,
    "LOAD_FAST_BORROW",
    "LOAD_FAST_BORROW_LOAD_FAST_BORROW",
)
MODIFY_FAST_NAMES = python3_13.MODIFY_FAST_NAMES
ACCESS_FAST_NAMES = LOAD_FAST_NAMES + MODIFY_FAST_NAMES

# Remaining opcodes
CALL_NAMES = python3_13.CALL_NAMES
OPERATION_NAMES = python3_13.OPERATION_NAMES

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
MODIFY_NAME_NAMES = python3_13.MODIFY_NAME_NAMES

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


def get_branch_type(opcode: int) -> bool | None:  # noqa: D103
    match opname[opcode]:
        case (
            "POP_JUMP_IF_TRUE"
            | "POP_JUMP_IF_NOT_NONE"
            | "INSTRUMENTED_POP_JUMP_IF_TRUE"
            | "INSTRUMENTED_POP_JUMP_IF_NOT_NONE"
        ):
            return True
        case (
            "POP_JUMP_IF_FALSE"
            | "POP_JUMP_IF_NONE"
            | "FOR_ITER"
            | "INSTRUMENTED_POP_JUMP_IF_FALSE"
            | "INSTRUMENTED_POP_JUMP_IF_NONE"
        ):
            return False
        case _:
            return None


def stack_effects(  # noqa: D103 C901
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffects:
    match opname[opcode]:
        case "JUMP_IF_FALSE" | "JUMP_IF_TRUE" | "NOT_TAKEN" | "INSTRUMENTED_NOT_TAKEN":
            return StackEffects(0, 0)
        case (
            "POP_ITER"
            | "INSTRUMENTED_POP_ITER"
            # TODO(lk): I don't understand why this worked in python3_12, as it pops 1.
            | "INSTRUMENTED_POP_JUMP_IF_TRUE"
            | "INSTRUMENTED_POP_JUMP_IF_FALSE"
            | "INSTRUMENTED_POP_JUMP_IF_NONE"
            | "INSTRUMENTED_POP_JUMP_IF_NOT_NONE"
        ):
            return StackEffects(1, 0)
        case "LOAD_COMMON_CONSTANT" | "LOAD_FAST_BORROW" | "LOAD_SMALL_INT":
            return StackEffects(0, 1)
        case "LOAD_SPECIAL" | "INSTRUMENTED_FOR_ITER":
            return StackEffects(1, 2)
        case "INSTRUMENTED_END_ASYNC_FOR":
            return StackEffects(2, 0)
        case "BUILD_TEMPLATE":
            return StackEffects(2, 1)
        case "LOAD_FAST_BORROW_LOAD_FAST_BORROW":
            return StackEffects(0, 2)
        case "BUILD_INTERPOLATION":
            pops = 3 if (arg is not None and (arg & 1)) else 2
            return StackEffects(pops, 1)
        case "BUILD_SLICE":
            assert arg is not None
            pops = 2 if arg == 2 else 3 if arg == 3 else arg  # else arg is not documented
            return StackEffects(pops, 1)
        case "INSTRUMENTED_CALL":
            assert arg is not None
            return StackEffects(2 + arg, 1)
        case "INSTRUMENTED_CALL_KW":
            assert arg is not None
            return StackEffects(3 + arg, 1)
        # TODO(lk): Not documented
        case "ANNOTATIONS_PLACEHOLDER":
            return StackEffects(0, 0)
        case "CALL_FUNCTION_EX" | "INSTRUMENTED_CALL_FUNCTION_EX":
            return StackEffects(3, 0)
        # TODO(lk): Not in line with documentation; doesn't make sense
        case "RETURN_VALUE" | "INSTRUMENTED_RETURN_VALUE":
            return StackEffects(1, 1) # if arg is None else StackEffects(1, 0)
        case _:
            return python3_13.stack_effects(opcode, arg, jump=jump)


class BranchCoverageInstrumentation(python3_12.BranchCoverageInstrumentation):
    """Branch coverage adapter for Python 3.14.

    Uses Python 3.12's for-loop handling (END_FOR) but adopts the 3.13
    comparison extraction to support *_CAST comparison ops introduced in
    newer Python versions.
    """

    extract_comparison = staticmethod(python3_13.extract_comparison)


LineCoverageInstrumentation = python3_13.LineCoverageInstrumentation


class Python314InstrumentationInstructionsGenerator(
    python3_13.Python313InstrumentationInstructionsGenerator
):
    """Generates instrumentation instructions for Python 3.14."""

    @classmethod
    def _generate_argument_instructions(
        cls,
        arg: InstrumentationArgument,
        position: int,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match arg:
            # case InstrumentedSmallIntLoad(value):
            #     return (cf.ArtificialInstr("LOAD_SMALL_INT", value, lineno=lineno),)
            # case InstrumentationFastLoad(name):
            #     return (cf.ArtificialInstr("LOAD_FAST_BORROW", name, lineno=lineno),)
            # case InstrumentationFastLoadTuple(names):
            #     return (
            #         cf.ArtificialInstr(
            #             "LOAD_FAST_BORROW_LOAD_FAST_BORROW", arg=names, lineno=lineno
            #         ),
            #         cf.ArtificialInstr("BUILD_TUPLE", 2, lineno=lineno),
            #     )
            case _:
                return super()._generate_argument_instructions(arg, position, lineno)

    # @classmethod
    # def generate_method_call_instructions(
    #     cls,
    #     method_call: InstrumentationMethodCall,
    #     lineno: int | _UNSET | None,
    # ) -> tuple[cf.ArtificialInstr, ...]:
    #     return (
    #         cf.ArtificialInstr("LOAD_CONST", method_call.self, lineno=lineno),
    #         cf.ArtificialInstr("LOAD_ATTR", (True, method_call.method_name), lineno=lineno),
    #         *chain(
    #             *(
    #                 cls._generate_argument_instructions(arg, position, lineno)
    #                 for position, arg in enumerate(method_call.args)
    #             )
    #         ),
    #         cf.ArtificialInstr("CALL", len(method_call.args), lineno=lineno),
    #     )


class CheckedCoverageInstrumentation(python3_13.CheckedCoverageInstrumentation):
    """Specialized instrumentation adapter for checked coverage in Python 3.14."""

    instructions_generator = Python314InstrumentationInstructionsGenerator

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:  # noqa: D102
        return super().should_instrument_line(instr, lineno)  # and instr.name != "POP_TOP"

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
        if instr.name not in ACCESS_FAST_NAMES:
            return super().visit_local_access(
                ast_info,
                cfg,
                code_object_id,
                node,
                instr,
                instr_index,
                instr_original_index,
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
            case "LOAD_FAST" | "LOAD_FAST_CHECK" | "STORE_FAST" | "LOAD_FAST_BORROW":
                # Instrumentation after the original instruction
                node.basic_block[after(instr_index)] = instructions

        return None

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
        OPERATION_NAMES: python3_13.CheckedCoverageInstrumentation.visit_generic,
        ACCESS_FAST_NAMES: visit_local_access,
        python3_12.ATTRIBUTES_NAMES: python3_13.CheckedCoverageInstrumentation.visit_attr_access,
        python3_10.ACCESS_SUBSCR_NAMES: python3_13.CheckedCoverageInstrumentation.visit_subscr_access,  # noqa: E501
        python3_12.ACCESS_SLICE_NAMES: python3_13.CheckedCoverageInstrumentation.visit_slice_access,
        python3_10.ACCESS_NAME_NAMES: python3_13.CheckedCoverageInstrumentation.visit_name_access,
        python3_12.IMPORT_NAME_NAMES: python3_13.CheckedCoverageInstrumentation.visit_import_name_access,  # noqa: E501
        python3_10.ACCESS_GLOBAL_NAMES: python3_13.CheckedCoverageInstrumentation.visit_global_access,  # noqa: E501
        python3_12.ACCESS_DEREF_NAMES: python3_13.CheckedCoverageInstrumentation.visit_deref_access,
        python3_12.JUMP_NAMES: python3_13.CheckedCoverageInstrumentation.visit_jump,
        CALL_NAMES: visit_call,
        python3_12.RETURNING_NAMES: python3_13.CheckedCoverageInstrumentation.visit_return,
    }


class DynamicSeedingInstrumentation(python3_13.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.14."""

    instructions_generator = Python314InstrumentationInstructionsGenerator
