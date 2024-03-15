#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Pynguin is an automated unit test generation framework for Python."""
import copyreg

import pynguin.configuration as config
import pynguin.generator as gen

from bytecode.instr import InstrLocation, _UNSET
from typing import Callable, Optional

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
    "__version__",
    "run_pynguin",
    "set_configuration",
]

def _pickle_instr_location(
    instr_location: InstrLocation
) -> tuple[
    Callable[[Optional[int], Optional[int], Optional[int], Optional[int]], InstrLocation],
    tuple[Optional[int], Optional[int], Optional[int], Optional[int]]
]:
    return InstrLocation, (
        instr_location.lineno,
        instr_location.end_lineno,
        instr_location.col_offset,
        instr_location.end_col_offset,
    )

copyreg.pickle(InstrLocation, _pickle_instr_location)


def _pickle_unset(
    unset: _UNSET
) -> tuple[Callable[[], _UNSET], tuple]:
    return _UNSET, tuple()

copyreg.pickle(_UNSET, _pickle_unset)
