#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
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

__all__ = [
    "Algorithm",
    "Configuration",
    "ExportStrategy",
    "StatisticsBackend",
    "TypeInferenceStrategy",
    "run_pynguin",
    "set_configuration",
]
