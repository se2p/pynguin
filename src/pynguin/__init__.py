#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Pynguin is an automated unit test generation framework for Python."""

import copyreg

from collections.abc import Callable

from bytecode.instr import _UNSET  # noqa: PLC2701
from bytecode.instr import InstrLocation

import pynguin.configuration as config
import pynguin.generator as gen


set_configuration = gen.set_configuration
run_pynguin = gen.run_pynguin
Configuration = config.Configuration
Algorithm = config.Algorithm
ExportStrategy = config.ExportStrategy
StatisticsBackend = config.StatisticsBackend
TypeInferenceStrategy = config.TypeInferenceStrategy

__all__ = [
    "Algorithm",
    "Configuration",
    "ExportStrategy",
    "StatisticsBackend",
    "TypeInferenceStrategy",
    "run_pynguin",
    "set_configuration",
]


# This function is required otherwise a FrozenInstanceError is raised
# because InstrLocation is a frozen dataclass that uses __slots__.
def _pickle_instr_location(
    instr_location: InstrLocation,
) -> tuple[
    Callable[[int | None, int | None, int | None, int | None], InstrLocation],
    tuple[int | None, int | None, int | None, int | None],
]:
    return InstrLocation, (
        instr_location.lineno,
        instr_location.end_lineno,
        instr_location.col_offset,
        instr_location.end_col_offset,
    )


copyreg.pickle(InstrLocation, _pickle_instr_location)


# This function is required otherwise a TypeError is raised
# because _UNSET is a singleton object and does not support pickle well.
def _pickle_unset(unset: _UNSET) -> tuple[Callable[[], _UNSET], tuple]:  # noqa: ARG001
    return _UNSET, ()


copyreg.pickle(_UNSET, _pickle_unset)
