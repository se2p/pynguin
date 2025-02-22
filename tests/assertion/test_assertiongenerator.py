#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

import pynguin.assertion.assertiongenerator as ag


@pytest.mark.parametrize("created,killed,timeout,score", [(5, 2, 1, 0.5), (1, 0, 1, 1.0)])
def test_mutation_score(created, killed, timeout, score):
    metrics = ag._MutationMetrics(created, killed, timeout)
    assert metrics.get_score() == score


@pytest.mark.parametrize(
    "inp, result",
    [
        (
            [ag._MutantInfo(0, [], [1])],
            ag._MutationMetrics(1, 1, 0),
        ),
        (
            [ag._MutantInfo(0, [], [1]), ag._MutantInfo(1, [0], [])],
            ag._MutationMetrics(2, 1, 1),
        ),
    ],
)
def test_compute_metrics(inp, result):
    assert ag._MutationSummary(inp).get_metrics() == result
