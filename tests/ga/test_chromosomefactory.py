#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testcasefactory as tcf
import pynguin.testsuite.testsuitechromosome as tsc


def test_get_chromosome():
    test_case_factory = MagicMock(tcf.TestCaseFactory)
    factory = cf.TestSuiteChromosomeFactory(test_case_factory)
    config.INSTANCE.min_initial_tests = 5
    config.INSTANCE.max_initial_tests = 5
    chromosome = factory.get_chromosome()
    assert (
        config.INSTANCE.min_initial_tests
        <= test_case_factory.get_test_case.call_count
        <= config.INSTANCE.max_initial_tests
    )
    assert isinstance(chromosome, tsc.TestSuiteChromosome)
