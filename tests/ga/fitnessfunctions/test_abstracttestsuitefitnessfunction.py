#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.ga.fitnessfunctions.abstracttestsuitefitnessfunction as atsff
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
from pynguin.ga.fitnessfunction import FitnessValues


class DummyTestSuiteFitnessFunction(atsff.AbstractTestSuiteFitnessFunction):
    def compute_fitness_values(self, individual) -> FitnessValues:
        pass  # pragma: no cover

    def is_maximisation_function(self) -> bool:
        return False  # pragma: no cover


def test_run_test_suite_chromosome():
    executor = MagicMock()
    result0 = MagicMock()
    result1 = MagicMock()
    result2 = MagicMock()
    executor.execute.side_effect = [result0, result1]
    ff = DummyTestSuiteFitnessFunction(executor)
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
    assert ff._run_test_suite_chromosome(indiv) == [result0, result1, result2]
    assert test_case0.get_last_execution_result() == result0
    assert test_case1.get_last_execution_result() == result1


def test_run_test_suite_chromosome_cache():
    executor = MagicMock()
    result0 = MagicMock()
    result1 = MagicMock()
    result2 = MagicMock()
    executor.execute.side_effect = [result0, result1]
    ff = DummyTestSuiteFitnessFunction(executor)
    indiv = tsc.TestSuiteChromosome()
    test_case0 = tcc.TestCaseChromosome(MagicMock())
    test_case0.set_changed(True)
    test_case0._fitness_values = {"foo": "bar"}
    test_case1 = tcc.TestCaseChromosome(MagicMock())
    test_case1.set_changed(False)
    test_case1._fitness_values = {"foo": "bar"}
    test_case2 = tcc.TestCaseChromosome(MagicMock())
    test_case2.set_changed(False)
    test_case2._fitness_values = {"foo": "bar"}
    test_case2.set_last_execution_result(result2)
    indiv.add_test_case_chromosome(test_case0)
    indiv.add_test_case_chromosome(test_case1)
    indiv.add_test_case_chromosome(test_case2)
    assert ff._run_test_suite_chromosome(indiv) == [result0, result1, result2]
    assert test_case0.fitness_values == {}
    assert test_case1.fitness_values == {}
    assert test_case2.fitness_values == {"foo": "bar"}
