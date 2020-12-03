#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.ga.chromosomeconverter as cc
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc


def test_no_result():
    converter = cc.ChromosomeConverter()
    assert converter.passing_test_suite.size() == 0
    assert converter.failing_test_suite.size() == 0


def test_simple_conversion():
    passing = tcc.TestCaseChromosome(dtc.DefaultTestCase())
    failing = tcc.TestCaseChromosome(dtc.DefaultTestCase())
    mocked_result = MagicMock()
    mocked_result.has_test_exceptions.return_value = True
    failing.set_last_execution_result(mocked_result)
    chromosome = tsc.TestSuiteChromosome()
    chromosome.add_test_case_chromosomes([failing, passing])

    converter = cc.ChromosomeConverter()
    chromosome.accept(converter)
    passing_suite = converter.passing_test_suite
    failing_suite = converter.failing_test_suite

    assert passing_suite.test_case_chromosomes == [passing]
    assert failing_suite.test_case_chromosomes == [failing]
