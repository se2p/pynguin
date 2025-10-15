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

from opcode import opname

from pynguin.instrumentation import StackEffects
from pynguin.instrumentation.version import python3_10
from pynguin.instrumentation.version import python3_11
from pynguin.instrumentation.version import python3_12
from pynguin.instrumentation.version import python3_13
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

from . import python3_12 as _prev12
from . import python3_13 as _prev


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
    "LOAD_FAST_LOAD_FAST",
    "STORE_FAST_LOAD_FAST",
)
MODIFY_FAST_NAMES = (
    *python3_13.MODIFY_FAST_NAMES,
    "STORE_FAST_STORE_FAST",
    "STORE_FAST_LOAD_FAST",
)
ACCESS_FAST_NAMES = (
    *python3_13.LOAD_FAST_NAMES,
    "LOAD_FAST_LOAD_FAST",
    *python3_13.MODIFY_FAST_NAMES,
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
    + python3_13.IMPORT_NAME_NAMES
    + python3_12.JUMP_NAMES
    + CALL_NAMES
    + python3_13.RETURNING_NAMES
)

MEMORY_USE_NAMES = (
    LOAD_FAST_NAMES
    + python3_13.LOAD_NAME_NAMES
    + python3_13.LOAD_GLOBAL_NAMES
    + python3_13.LOAD_DEREF_NAMES
    + python3_12.LOAD_ATTR_NAMES
    + python3_13.IMPORT_FROM_NAMES
    + python3_10.LOAD_METHOD_NAMES
    + python3_13.CLOSURE_LOAD_NAMES
    + python3_10.BINARY_SUBSCR_NAMES
    + python3_12.BINARY_SLICE_NAMES
)
MEMORY_DEF_NAMES = (
    MODIFY_FAST_NAMES
    + python3_13.MODIFY_NAME_NAMES
    + python3_13.MODIFY_GLOBAL_NAMES
    + python3_13.MODIFY_DEREF_NAMES
    + python3_10.MODIFY_ATTR_NAMES
    + python3_13.IMPORT_NAME_NAMES  # compensate incorrect stack effect for IMPORT_NAME
    + python3_10.ACCESS_SUBSCR_NAMES
    + python3_12.ACCESS_SLICE_NAMES
)


def stack_effects(  # noqa: D103
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffects:
    match opname[opcode]:
        case "JUMP_IF_FALSE" | "JUMP_IF_TRUE":
            return StackEffects(0, 0)
        case (
            "INSTRUMENTED_POP_JUMP_IF_TRUE"
            | "INSTRUMENTED_POP_JUMP_IF_FALSE"
            | "INSTRUMENTED_POP_JUMP_IF_NONE"
            | "INSTRUMENTED_POP_JUMP_IF_NOT_NONE"
            | "INSTRUMENTED_RETURN_VALUE"
        ):
            return StackEffects(1, 0)
        case (
            "LOAD_COMMON_CONSTANT"
            | "LOAD_FAST_BORROW"
            | "LOAD_SMALL_INT"
            | "LOAD_SPECIAL"
            | "INSTRUMENTED_FOR_ITER"
        ):
            return StackEffects(0, 1)
        case "INSTRUMENTED_END_ASYNC_FOR":
            return StackEffects(2, 0)
        case "LOAD_FAST_BORROW_LOAD_FAST_BORROW":
            return StackEffects(0, 2)
        case "BUILD_INTERPOLATION":
            pops = 3 if (arg & 1) else 2
            return StackEffects(pops, 1)
        case "BUILD_SLICE":
            return StackEffects(arg, 1)
        case "INSTRUMENTED_CALL":
            pops = (arg + 1) if arg is not None else 1
            return StackEffects(pops, 0)
        case "INSTRUMENTED_CALL_KW":
            pops = (arg + 3) if arg is not None else 1
            pushes = 1
            return StackEffects(pops, pushes)
        case _:
            return python3_13.stack_effects(opcode, arg, jump=jump)


# For Python 3.14, some for-loop end handling matches Python 3.12 (END_FOR)
# rather than the POP_TOP pattern used by our 3.13 adapter. Prefer the 3.12
# adapters to keep semantics correct for loops and line instrumentation.
class BranchCoverageInstrumentation(_prev12.BranchCoverageInstrumentation):
    """Branch coverage adapter for Python 3.14.

    Uses Python 3.12's for-loop handling (END_FOR) but adopts the 3.13
    comparison extraction to support *_CAST comparison ops introduced in
    newer Python versions.
    """

    extract_comparison = staticmethod(_prev.extract_comparison)


LineCoverageInstrumentation = _prev.LineCoverageInstrumentation
CheckedCoverageInstrumentation = _prev.CheckedCoverageInstrumentation
Python314InstrumentationInstructionsGenerator = _prev.Python313InstrumentationInstructionsGenerator


class DynamicSeedingInstrumentation(python3_13.DynamicSeedingInstrumentation):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.13."""

    instructions_generator = Python314InstrumentationInstructionsGenerator

    STRING_FUNC_POS = -4

    STRING_FUNC_POS_WITH_ARG = -5
