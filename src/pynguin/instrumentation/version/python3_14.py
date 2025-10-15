#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.14.

According to the Python3.14.md summary, there are no explicit opcode or
bytecode semantic changes that impact our instrumentation compared to 3.13.
Thus, Python 3.14 reuses the Python 3.13 implementation.
"""

from __future__ import annotations

import dis

from pynguin.instrumentation import StackEffects as _StackEffects

from . import python3_12 as _prev12
from . import python3_13 as _prev


# Re-export all public symbols of the 3.13 implementation in this module's
# namespace, so code importing from python3_14 continues to work transparently.
for _name in getattr(_prev, "__all__", ()):  # pragma: no cover - simple aliasing
    globals()[_name] = getattr(_prev, _name)

# Public exports mirror 3.13.
__all__ = list(getattr(_prev, "__all__", ()))


def stack_effects(opcode: int, arg: int | None, *, jump: bool = False) -> _StackEffects:
    """Return stack effects for Python 3.14.

    Delegates to the Python 3.13 implementation and falls back to dis.stack_effect
    for any new 3.14-specific opcodes that the previous implementation does not
    explicitly recognize.
    """
    try:
        prev = _prev.stack_effects(opcode, arg, jump=jump)
    except AssertionError:
        # Unknown to previous version; compute net effect and map to a simple pair.
        net = dis.stack_effect(opcode, arg if arg is not None else 0, jump=jump)
        return _StackEffects(0, net) if net >= 0 else _StackEffects(-net, 0)
    else:
        expected = dis.stack_effect(opcode, arg if arg is not None else 0, jump=jump)
        net_prev = prev.pushes - prev.pops
        if net_prev != expected:
            return _StackEffects(0, expected) if expected >= 0 else _StackEffects(-expected, 0)
        return prev


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
