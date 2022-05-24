#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Pynguin is an automated unit test generation framework for Python."""
import pynguin.configuration as config
import pynguin.generator as gen

set_configuration = gen.set_configuration
run_pynguin = gen.run_pynguin
Configuration = config.Configuration
Algorithm = config.Algorithm
ExportStrategy = config.ExportStrategy
StatisticsBackend = config.StatisticsBackend
TypeInferenceStrategy = config.TypeInferenceStrategy

__version__ = "0.20.0"
__all__ = [
    "set_configuration",
    "run_pynguin",
    "Configuration",
    "__version__",
    "Algorithm",
    "ExportStrategy",
    "StatisticsBackend",
    "TypeInferenceStrategy",
]
