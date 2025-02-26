#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

from pynguin.ga import chromosome as chrom
from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
from pynguin.ga.stoppingcondition import MaxStatementExecutionsStoppingCondition


class DummyAlgorithm(GenerationAlgorithm):
    def generate_tests(self) -> chrom.Chromosome:
        pass  # pragma: no cover


def test_progress(result):
    strategy = DummyAlgorithm()
    stopping = MaxStatementExecutionsStoppingCondition(100)
    stopping.set_limit(10)
    stopping.after_remote_test_case_execution(None, result)
    strategy.stopping_conditions = [stopping]
    assert strategy.progress() == 0.1


def test_add_search_observer():
    strategy = DummyAlgorithm()
    obs = MagicMock()
    strategy.add_search_observer(obs)
    assert strategy._search_observers == [obs]
