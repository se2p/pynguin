#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.ga.fitnessfunctions.abstractsuitefitnessfunction as asff
import pynguin.ga.testcasechromosome as tcc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.ga.fitnessfunction import FitnessValues


class DummySuiteFitnessFunction(asff.AbstractSuiteFitnessFunction):
    def compute_fitness_values(self, individual) -> FitnessValues:
        pass

    def is_maximisation_function(self) -> bool:
        pass


def test_run_test_suite():
    executor = MagicMock()
    result0 = MagicMock()
    result1 = MagicMock()
    result2 = MagicMock()
    executor.execute.side_effect = [result0, result1]
    ff = DummySuiteFitnessFunction(executor)
    indiv = tsc.TestSuiteChromosome()
    test_case0 = tcc.TestCaseChromosome(MagicMock())
    test_case0.set_changed(True)
    test_case1 = tcc.TestCaseChromosome(MagicMock())
    test_case1.set_changed(False)
    test_case2 = tcc.TestCaseChromosome(MagicMock())
    test_case2.set_changed(False)
    test_case2.set_last_execution_result(result2)
    indiv.add_test_case_chromosome(test_case0)
    indiv.add_test_case_chromosome(test_case1)
    indiv.add_test_case_chromosome(test_case2)
    assert ff._run_test_suite(indiv) == [result0, result1, result2]
    assert test_case0.get_last_execution_result() == result0
    assert test_case1.get_last_execution_result() == result1
