#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.ga.testsuitechromosome as tsc
import pynguin.ga.testsuitechromosomefactory as tscf


def test_get_chromosome():
    test_case_chromosome_factory = MagicMock(tccf.TestCaseChromosomeFactory)
    factory = tscf.TestSuiteChromosomeFactory(test_case_chromosome_factory)
    config.configuration.min_initial_tests = 5
    config.configuration.max_initial_tests = 5
    chromosome = factory.get_chromosome()
    assert (
        config.configuration.min_initial_tests
        <= test_case_chromosome_factory.get_chromosome.call_count
        <= config.configuration.max_initial_tests
    )
    assert isinstance(chromosome, tsc.TestSuiteChromosome)
