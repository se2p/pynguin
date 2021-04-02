#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
"""Provides the DynaMOSA test-generation strategy."""
import logging

import pynguin.ga.chromosome as chrom
from pynguin.generation.algorithms.abstractmosastrategy import AbstractMOSATestStrategy


class DynaMOSATestStrategy(AbstractMOSATestStrategy):
    """Implements the Dynamic Many-Objective Sorting Algorithm DynaMOSA."""

    _logger = logging.getLogger(__name__)

    def generate_tests(self) -> chrom.Chromosome:
        pass

    def evolve(self) -> None:
        """Runs one evolution step."""
