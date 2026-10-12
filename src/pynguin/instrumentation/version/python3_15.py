#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.15."""

from __future__ import annotations

from opcode import opname
from typing import TYPE_CHECKING, ClassVar

from pynguin.instrumentation import StackEffects, tracer
from pynguin.instrumentation.version import python3_12, python3_14
from pynguin.instrumentation.version.common import (
    CheckedCoverageInstrumentationVisitorMethod,
    InstrumentationConstantLoad,
    InstrumentationMethodCall,
    InstrumentationSetupAction,
    InstrumentationStackValue,
    after,
)
from pynguin.instrumentation.version.python3_14 import (
    ACCESS_NAMES,
    CALL_NAMES,
    CLOSURE_LOAD_NAMES,
    COND_BRANCH_NAMES,
    IMPORT_FROM_NAMES,
    IMPORT_NAME_NAMES,
    LOAD_DEREF_NAMES,
    LOAD_FAST_NAMES,
    LOAD_GLOBAL_NAMES,
    LOAD_NAME_NAMES,
    MEMORY_DEF_NAMES,
    MEMORY_USE_NAMES,
    MODIFY_DEREF_NAMES,
    MODIFY_FAST_NAMES,
    MODIFY_GLOBAL_NAMES,
    MODIFY_NAME_NAMES,
    RETURN_NONE_SIZE,
    RETURNING_NAMES,
    STORE_NAME_NAMES,
    STORE_NAMES,
    TRACED_NAMES,
    YIELDING_NAMES,
    add_for_loop_no_yield_nodes,
    get_branch_type,
    is_conditional_jump,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bytecode.instr import Instr

    from pynguin.instrumentation import controlflow as cf
    from pynguin.instrumentation import transformer


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


def end_with_explicit_return_none(instructions: Sequence[Instr]) -> bool:  # noqa: D103
    # In Python 3.15, None is loaded with "LOAD_COMMON_CONSTANT None" instead of
    # "LOAD_CONST None".
    return (
        len(instructions) >= 3
        # check if the "return None" is implicit or explicit
        and instructions[-3].lineno != instructions[-2].lineno
        and instructions[-2].name == "LOAD_COMMON_CONSTANT"
        # The bytecode library only defines CommonConstant.CONSTANT_NONE for Python 3.15+.
        and getattr(instructions[-2].arg, "name", None) == "CONSTANT_NONE"
        and instructions[-1].name == "RETURN_VALUE"
    )


def stack_effects(  # noqa: D103
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffects:
    # In Python 3.15, an iterator takes two stack slots: the iterator itself and either
    # NULL or the index of the next item (sequences are iterated without creating an
    # iterator object). This changes the stack effects of all instructions that create,
    # advance, or remove an iterator, including the ones of "yield from" and "await".
    match opname[opcode]:
        case "TRACE_RECORD":
            return StackEffects(0, 0)
        case "GET_ITER":
            return StackEffects(1, 2)
        case "FOR_ITER" | "INSTRUMENTED_FOR_ITER":
            return StackEffects(2, 3)
        case "POP_ITER" | "INSTRUMENTED_POP_ITER":
            return StackEffects(2, 0)
        case "SEND":
            return StackEffects(3, 3)
        case "END_SEND" | "INSTRUMENTED_END_SEND":
            return StackEffects(3, 1)
        case "CLEANUP_THROW":
            return StackEffects(4, 3)
        case _:
            return python3_14.stack_effects(opcode, arg, jump=jump)


def extract_import_name(arg: object) -> object:
    """Extract the module name from the argument of an IMPORT_NAME instruction.

    Starting with Python 3.15, the argument of IMPORT_NAME also encodes whether the
    import is lazy or eager, so the bytecode library represents it as a
    ``(bool, bool, name)`` tuple.

    Args:
        arg: The argument of the IMPORT_NAME instruction.

    Returns:
        The module name, or the argument itself if it has another shape.
    """
    match arg:
        case (bool(), bool(), str(name)):
            return name
        case _:
            return arg


class CheckedCoverageInstrumentation(python3_14.CheckedCoverageInstrumentation):
    """Specialized instrumentation adapter for checked coverage in Python 3.15."""

    def visit_import_name_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        node.basic_block[after(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.COPY_FIRST,
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
                    InstrumentationConstantLoad(value=extract_import_name(instr.arg)),  # type: ignore[arg-type]
                    InstrumentationStackValue.FIRST,
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
        **python3_14.CheckedCoverageInstrumentation.METHODS,
        python3_12.IMPORT_NAME_NAMES: visit_import_name_access,
    }


class BranchCoverageInstrumentation(python3_14.BranchCoverageInstrumentation):
    """Branch coverage adapter for Python 3.15."""


class LineCoverageInstrumentation(python3_14.LineCoverageInstrumentation):
    """Specialized instrumentation adapter for line coverage in Python 3.15."""


class DynamicSeedingInstrumentation(python3_14.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.15."""
