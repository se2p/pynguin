#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.ga.fitnessfunctions.abstracttestcasefitnessfunction as atcff
import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.fitnessfunction import FitnessValues


class DummyTestSuiteFitnessFunction(atcff.AbstractTestCaseFitnessFunction):
    def compute_fitness_values(self, individual) -> FitnessValues:
        pass  # pragma: no cover

    def is_maximisation_function(self) -> bool:
        pass  # pragma: no cover


def test_run_test_case_chromosome_no_result():
    executor = MagicMock()
    result0 = MagicMock()
    executor.execute.return_value = result0
    ff = DummyTestSuiteFitnessFunction(executor, code_object_id=0)
    test_case0 = tcc.TestCaseChromosome(MagicMock())
    test_case0.set_changed(True)
    assert ff._run_test_case_chromosome(test_case0) == result0
    assert test_case0.get_last_execution_result() == result0


def test_run_test_case_chromosome_has_result():
    executor = MagicMock()
    result0 = MagicMock()
    executor.execute.return_value = result0
    ff = DummyTestSuiteFitnessFunction(executor, code_object_id=0)
    test_case0 = tcc.TestCaseChromosome(MagicMock())
    test_case0.set_changed(False)
    test_case0.set_last_execution_result(result0)
    assert ff._run_test_case_chromosome(test_case0) == result0
    assert test_case0.get_last_execution_result() == result0
