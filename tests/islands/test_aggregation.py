#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.testcase as tc
import pynguin.utils.statistics.stats as stat
from pynguin import generator
from pynguin.generator import ReturnCode
from pynguin.islands import aggregation
from pynguin.islands.island import IslandResult
from pynguin.slicer.statementslicingobserver import RemoteStatementSlicingObserver
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def _fake_test_case(source: str) -> tc.TestCase:
    test_case = MagicMock(spec=tc.TestCase)
    test_case.to_code.return_value = source
    return test_case


def test_deduplicate_by_source_drops_identical_test_cases():
    shared = _fake_test_case("def test_0():\n    pass\n")
    duplicate = _fake_test_case("def test_0():\n    pass\n")
    distinct = _fake_test_case("def test_1():\n    pass\n")
    results = [
        IslandResult(0, [shared, distinct], ReturnCode.OK),
        IslandResult(1, [duplicate], ReturnCode.OK),
    ]

    deduplicated = aggregation._deduplicate_by_source(results)

    assert len(deduplicated) == 2
    assert shared in deduplicated
    assert distinct in deduplicated
    assert duplicate not in deduplicated  # first-island-wins on a hash collision


def test_deduplicate_by_source_keeps_all_distinct_test_cases():
    test_cases = [_fake_test_case(f"def test_{i}():\n    pass\n") for i in range(3)]
    results = [IslandResult(0, test_cases, ReturnCode.OK)]

    deduplicated = aggregation._deduplicate_by_source(results)

    assert len(deduplicated) == 3


def test_deduplicate_by_source_handles_empty_results():
    assert aggregation._deduplicate_by_source([]) == []
    assert aggregation._deduplicate_by_source([IslandResult(0, [], ReturnCode.OK)]) == []


def test_assemble_final_suite_tracks_dedup_statistics(monkeypatch):
    monkeypatch.setattr(generator, "_instantiate_test_generation_strategy", MagicMock())
    monkeypatch.setattr(
        generator, "finalize_generation_result", MagicMock(return_value=ReturnCode.OK)
    )
    monkeypatch.setattr(tcc, "TestCaseChromosome", MagicMock())
    results = [
        IslandResult(
            0,
            [
                _fake_test_case("def test_0():\n    pass\n"),
                _fake_test_case("def test_1():\n    pass\n"),
            ],
            ReturnCode.OK,
        ),
        IslandResult(1, [_fake_test_case("def test_0():\n    pass\n")], ReturnCode.OK),
        IslandResult(2, [_fake_test_case("def test_1():\n    pass\n")], ReturnCode.OK),
    ]

    return_code = aggregation.assemble_final_suite(results, MagicMock(), MagicMock(), MagicMock())

    tracked = dict(stat.statistics_tracker.variables_generator)
    assert return_code is ReturnCode.OK
    assert tracked[RuntimeVariable.IslandsMerged] == 3
    assert tracked[RuntimeVariable.IslandTestCasesBeforeDedup] == 4
    assert tracked[RuntimeVariable.IslandTestCasesAfterDedup] == 2
    assert tracked[RuntimeVariable.IslandDuplicateTestCasesRemoved] == 2


def _prepare_with_coverage_metrics(monkeypatch, coverage_metrics):
    executor = MagicMock()
    monkeypatch.setattr(generator, "_verify_config", MagicMock())
    monkeypatch.setattr(
        generator, "_setup_and_check", MagicMock(return_value=(executor, MagicMock(), MagicMock()))
    )
    base_configuration = config.Configuration(
        module_name="example",
        project_path=".",
        test_case_output=config.TestCaseOutputConfiguration(output_path="."),
        search_algorithm=config.SearchAlgorithmConfiguration(coverage_metrics=coverage_metrics),
    )
    return executor, aggregation.prepare_orchestrator_setup(base_configuration)


def test_prepare_orchestrator_setup_adds_the_slicing_observer_for_checked_coverage(monkeypatch):
    executor, setup_result = _prepare_with_coverage_metrics(
        monkeypatch, [config.CoverageMetric.CHECKED]
    )

    assert setup_result is not None
    executor.add_remote_observer.assert_called_once()
    assert isinstance(
        executor.add_remote_observer.call_args.args[0], RemoteStatementSlicingObserver
    )


def test_prepare_orchestrator_setup_adds_no_slicing_observer_for_branch_coverage(monkeypatch):
    executor, _setup_result = _prepare_with_coverage_metrics(
        monkeypatch, [config.CoverageMetric.BRANCH]
    )

    executor.add_remote_observer.assert_not_called()


def test_prepare_orchestrator_setup_returns_none_when_setup_fails(monkeypatch):
    monkeypatch.setattr(generator, "_verify_config", MagicMock())
    monkeypatch.setattr(generator, "_setup_and_check", MagicMock(return_value=None))

    assert (
        aggregation.prepare_orchestrator_setup(
            config.Configuration(
                module_name="example",
                project_path=".",
                test_case_output=config.TestCaseOutputConfiguration(output_path="."),
            )
        )
        is None
    )
