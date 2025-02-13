#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock
from unittest.mock import MagicMock

import pynguin.ga.operators.crossover as cross
import pynguin.ga.testsuitechromosome as tsc


def test_single_point_relative_crossover_to_small():
    crossover = cross.SinglePointRelativeCrossOver()
    parent1 = MagicMock(tsc.TestSuiteChromosome)
    parent1.size.return_value = 1
    parent2 = MagicMock(tsc.TestSuiteChromosome)
    parent2.size.return_value = 1
    crossover.cross_over(parent1, parent2)
    parent1.cross_over.assert_not_called()
    parent2.cross_over.assert_not_called()


def test_single_point_relative_crossover():
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.7
        crossover = cross.SinglePointRelativeCrossOver()
        parent1 = MagicMock(tsc.TestSuiteChromosome)
        parent1.size.return_value = 10
        parent2 = MagicMock(tsc.TestSuiteChromosome)
        parent2.size.return_value = 20
        clone1 = MagicMock(tsc.TestSuiteChromosome)
        clone2 = MagicMock(tsc.TestSuiteChromosome)
        parent1.clone.return_value = clone1
        parent2.clone.return_value = clone2
        crossover.cross_over(parent1, parent2)
        parent1.cross_over.assert_called_with(clone2, 7, 14)
        parent2.cross_over.assert_called_with(clone1, 14, 7)
