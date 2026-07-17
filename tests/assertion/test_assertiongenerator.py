#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st

import pynguin.assertion.assertiongenerator as ag
import pynguin.configuration as config
import pynguin.testcase.execution as ex
from pynguin.instrumentation.tracer import ExecutionTrace, SubjectProperties


class _FakeResult:
    def __init__(self, *, timeout=False):
        self.timeout = timeout


def _executor_mock():
    executor = MagicMock()
    # No test cases -> the strict-zip loops iterate over an empty result list.
    executor.execute_multiple.return_value = []
    return executor


def test_filtering_executor_defaults_to_plain_executor():
    plain = _executor_mock()
    generator = ag.AssertionGenerator(plain)
    assert generator._filtering_executor is plain


def test_filtering_executor_uses_supplied_executor():
    plain = _executor_mock()
    filtering = _executor_mock()
    generator = ag.AssertionGenerator(plain, filtering_executor=filtering)
    assert generator._filtering_executor is filtering


def test_capture_and_filtering_run_on_separate_executors():
    # The capture pass runs once on the plain executor; the filtering pass runs
    # ``filtering_executions`` times on the (fresh-process) filtering executor.
    plain = _executor_mock()
    filtering = _executor_mock()
    generator = ag.AssertionGenerator(plain, filtering_executions=2, filtering_executor=filtering)

    generator._add_assertions([])

    plain.execute_multiple.assert_called_once()
    assert filtering.execute_multiple.call_count == 2


def test_create_filtering_executor_disabled(monkeypatch):
    monkeypatch.setattr(
        config.configuration.test_case_output, "filter_assertions_in_subprocess", False
    )
    assert ag.create_filtering_executor(_executor_mock()) is None


def test_create_filtering_executor_already_subprocess(monkeypatch):
    monkeypatch.setattr(
        config.configuration.test_case_output, "filter_assertions_in_subprocess", True
    )
    subprocess_executor = MagicMock(spec=ex.SubprocessTestCaseExecutor)
    assert ag.create_filtering_executor(subprocess_executor) is None


def test_create_filtering_executor_builds_subprocess_executor(monkeypatch):
    monkeypatch.setattr(
        config.configuration.test_case_output, "filter_assertions_in_subprocess", True
    )
    # A plain (non-subprocess) executor yields a fresh subprocess filtering executor.
    # Construction does not spawn a process; that only happens on execution.
    result = ag.create_filtering_executor(MagicMock(spec=ex.TestCaseExecutor))
    assert isinstance(result, ex.SubprocessTestCaseExecutor)


def test_create_filtering_executor_accepts_traces_of_instrumented_code(monkeypatch):
    # Regression: the filtering executor used to be built with empty registries, so
    # every trace produced by instrumented code was rejected with "Code object id N
    # not registered in subject properties". In a subprocess that exception was
    # swallowed, the process exited 0 without a result, and the parent reported the
    # catch-all "Bug in Pynguin!".
    monkeypatch.setattr(
        config.configuration.test_case_output, "filter_assertions_in_subprocess", True
    )
    plain_properties = SubjectProperties()
    code_object_id = plain_properties.create_code_object_id()
    plain_properties.register_code_object(code_object_id, MagicMock())
    plain = MagicMock(spec=ex.TestCaseExecutor)
    plain.subject_properties = plain_properties

    filtering = ag.create_filtering_executor(plain)

    trace = ExecutionTrace()
    trace.executed_code_objects.add(code_object_id)
    filtering.subject_properties.validate_execution_trace(trace)


def test_create_filtering_executor_traces_independently_of_the_search(monkeypatch):
    monkeypatch.setattr(
        config.configuration.test_case_output, "filter_assertions_in_subprocess", True
    )
    plain_properties = SubjectProperties()
    plain = MagicMock(spec=ex.TestCaseExecutor)
    plain.subject_properties = plain_properties

    filtering = ag.create_filtering_executor(plain)

    assert (
        filtering.subject_properties.instrumentation_tracer
        is not plain_properties.instrumentation_tracer
    )


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


def test_select_minimal_assertions_empty():
    assert ag._select_minimal_assertions({}) == set()


def test_select_minimal_assertions_drops_assertion_killing_nothing():
    kill_map = {(0, 0): {1, 2}, (0, 1): set()}
    assert ag._select_minimal_assertions(kill_map) == {(0, 0)}


def test_select_minimal_assertions_identical_kills_keeps_one():
    # Two assertions killing exactly the same mutants -> keep exactly one.
    kill_map = {(0, 0): {1, 2}, (0, 1): {1, 2}}
    assert ag._select_minimal_assertions(kill_map) == {(0, 0)}


def test_select_minimal_assertions_subset_dropped():
    # (0, 1) kills a subset of what (0, 0) kills -> only the superset is kept.
    kill_map = {(0, 0): {1, 2, 3}, (0, 1): {2}}
    assert ag._select_minimal_assertions(kill_map) == {(0, 0)}


def test_select_minimal_assertions_disjoint_keeps_both():
    kill_map = {(0, 0): {1}, (0, 1): {2}}
    assert ag._select_minimal_assertions(kill_map) == {(0, 0), (0, 1)}


def test_select_minimal_assertions_tie_break_lowest_index():
    # Both cover the whole universe -> the lowest key is chosen deterministically.
    kill_map = {(1, 0): {1, 2}, (0, 0): {1, 2}}
    assert ag._select_minimal_assertions(kill_map) == {(0, 0)}


def test_select_minimal_assertions_covers_universe():
    kill_map = {(0, 0): {1, 2}, (0, 1): {2, 3}, (0, 2): {4}}
    keep = ag._select_minimal_assertions(kill_map)
    covered: set[int] = set()
    for key in keep:
        covered |= kill_map[key]
    assert covered == {1, 2, 3, 4}


@given(
    st.dictionaries(
        keys=st.tuples(
            st.integers(min_value=0, max_value=5), st.integers(min_value=0, max_value=5)
        ),
        values=st.sets(st.integers(min_value=0, max_value=20), max_size=8),
        max_size=12,
    )
)
def test_select_minimal_assertions_invariants(kill_map):
    keep = ag._select_minimal_assertions(kill_map)

    universe: set[int] = set()
    for kills in kill_map.values():
        universe |= kills

    # Mutation score preserved: the kept assertions cover the whole universe.
    covered: set[int] = set()
    for key in keep:
        covered |= kill_map[key]
    assert covered == universe

    # Only kill-bearing assertions are ever kept.
    assert all(kill_map[key] for key in keep)

    # Minimality: dropping any kept assertion loses coverage.
    for key in keep:
        others: set[int] = set()
        for other in keep:
            if other != key:
                others |= kill_map[other]
        assert not kill_map[key] <= others
