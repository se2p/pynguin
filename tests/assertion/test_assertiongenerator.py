#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

import pynguin.assertion.assertiongenerator as ag


class _FakeResult:
    def __init__(self, *, timeout=False):
        self.timeout = timeout


@pytest.mark.parametrize("created,killed,timeout,score", [(5, 2, 1, 0.5), (1, 0, 1, 1.0)])
def test_mutation_score(created, killed, timeout, score):
    metrics = ag._MutationMetrics(created, killed, timeout)
    assert metrics.get_score() == score


def test_abort_after_first_timeout_stops_consuming_and_pads():
    consumed = []

    def results():
        for result in [
            _FakeResult(),
            _FakeResult(timeout=True),
            _FakeResult(),
            _FakeResult(),
        ]:
            consumed.append(result)
            yield result

    out = list(ag.MutationAnalysisAssertionGenerator._abort_after_first_timeout(results(), 4))

    # The generator is not consumed past the first timeout ...
    assert len(consumed) == 2
    # ... but the result shape is preserved by padding with None.
    assert len(out) == 4
    assert out[0].timeout is False
    assert out[1].timeout is True
    assert out[2] is None
    assert out[3] is None


def test_abort_after_first_timeout_without_timeout_passes_through():
    results = [_FakeResult(), _FakeResult()]
    out = list(ag.MutationAnalysisAssertionGenerator._abort_after_first_timeout(iter(results), 2))
    assert out == results


def test_score_excludes_unchecked_mutants():
    # Only the two checked mutants (one killed, one survived) form the denominator;
    # a third, unchecked mutant never enters the summary and cannot fake-survive.
    summary = ag._MutationSummary([
        ag._MutantInfo(0, timed_out_by=[], killed_by=[1]),
        ag._MutantInfo(1, timed_out_by=[], killed_by=[]),
    ])
    assert summary.get_metrics() == ag._MutationMetrics(2, 1, 0)
    assert summary.get_metrics().get_score() == 0.5


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
