#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Pynguin is an automated unit test generation framework for Python."""
import pynguin.configuration as config
import pynguin.generator as gen

Pynguin = gen.Pynguin
Configuration = config.Configuration
Algorithm = config.Algorithm
ExportStrategy = config.ExportStrategy
StatisticsBackend = config.StatisticsBackend
StoppingCondition = config.StoppingCondition
TypeInferenceStrategy = config.TypeInferenceStrategy

__version__ = "0.7.0"
__all__ = [
    "Pynguin",
    "Configuration",
    "__version__",
    "Algorithm",
    "ExportStrategy",
    "StatisticsBackend",
    "StoppingCondition",
    "TypeInferenceStrategy",
]
