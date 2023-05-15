#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

from pynguin.ga import chromosome as chrom
from pynguin.ga.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxStatementExecutionsStoppingCondition,
)


class DummyTestStrategy(TestGenerationStrategy):
    def generate_tests(self) -> chrom.Chromosome:
        pass  # pragma: no cover


def test_progress():
    strategy = DummyTestStrategy()
    stopping = MaxStatementExecutionsStoppingCondition(100)
    stopping.set_limit(10)
    stopping.before_statement_execution(None, None, None)
    strategy.stopping_conditions = [stopping]
    assert strategy.progress() == 0.1


def test_add_search_observer():
    strategy = DummyTestStrategy()
    obs = MagicMock()
    strategy.add_search_observer(obs)
    assert strategy._search_observers == [obs]
