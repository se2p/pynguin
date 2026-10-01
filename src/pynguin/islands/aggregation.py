#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Merges island results into one deduplicated, exported test suite."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.stats as stat
from pynguin import generator
from pynguin.generator import ReturnCode, set_configuration
from pynguin.islands.migration import compute_test_case_hash
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.analyses.constants import ConstantProvider
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.islands.island import IslandResult
    from pynguin.testcase.execution import TestCaseExecutor

_LOGGER = logging.getLogger(__name__)


def _deduplicate_by_source(results: list[IslandResult]) -> list[tc.TestCase]:
    """Remove duplicate test cases produced by different islands.

    Test cases are compared using their source code without generated assertions.
    This avoids treating the same test as different only because its assertions
    differ between islands.

    Args:
        results: One IslandResult per island.

    Returns:
        The deduplicated test cases, first-island-wins on hash collisions.
    """
    seen: dict[str, tc.TestCase] = {}
    for result in results:
        for test_case in result.test_cases:
            seen.setdefault(compute_test_case_hash(test_case), test_case)
    return list(seen.values())


def prepare_orchestrator_setup(
    base_configuration: config.Configuration,
) -> tuple[TestCaseExecutor, ModuleTestCluster, ConstantProvider] | None:
    """Set up the orchestrator before starting the island processes.

    The SUT is imported before collecting island results because the returned test
    cases may reference SUT modules and functions during deserialization.

    The configuration is also validated before any island search is started. The
    executor gets the same observers as in a single-process run, e.g., the slicing
    observer checked coverage needs; the forked islands inherit them.

    Args:
        base_configuration: The configuration used for the search.

    Returns:
        The orchestrator executor, test cluster, and constant provider, or ``None``
        if setup fails.

    Raises:
        ConfigurationException: If the configuration is invalid.
    """
    set_configuration(base_configuration)
    generator._verify_config()  # noqa: SLF001
    setup_result = generator._setup_and_check()  # noqa: SLF001
    if setup_result is not None:
        generator._add_slicing_observer_if_needed(setup_result[0])  # noqa: SLF001
    return setup_result


def assemble_final_suite(
    results: list[IslandResult],
    executor: TestCaseExecutor,
    test_cluster: ModuleTestCluster,
    constant_provider: ConstantProvider,
) -> ReturnCode:
    """Merge the island results into a single test suite.

    Duplicate test cases are removed before creating chromosomes with the
    orchestrator's executor and fitness functions. Process-local island state is
    not reused.

    The merged suite is then finalized using the same steps as the single-process
    search. The number of merged islands and test cases before and after
    deduplication are tracked as output variables.

    Args:
        results: One IslandResult per island.
        executor: The orchestrator's executor.
        test_cluster: The orchestrator's test cluster.
        constant_provider: The orchestrator's constant provider.

    Returns:
        The result of exporting the merged suite.
    """
    deduplicated = _deduplicate_by_source(results)
    num_before_dedup = sum(len(result.test_cases) for result in results)
    _LOGGER.info(
        "Merging %d islands: %d test cases before dedup, %d after",
        len(results),
        num_before_dedup,
        len(deduplicated),
    )
    stat.track_output_variable(RuntimeVariable.IslandsMerged, len(results))
    stat.track_output_variable(RuntimeVariable.IslandTestCasesBeforeDedup, num_before_dedup)
    stat.track_output_variable(RuntimeVariable.IslandTestCasesAfterDedup, len(deduplicated))
    stat.track_output_variable(
        RuntimeVariable.IslandDuplicateTestCasesRemoved, num_before_dedup - len(deduplicated)
    )

    # Built only to harvest correctly-wired test_factory/fitness/coverage functions
    # via the existing factory code path -- never run, since these test cases were
    # already found by the islands' own searches.
    strategy = generator._instantiate_test_generation_strategy(  # noqa: SLF001
        executor, test_cluster, constant_provider
    )

    chromosomes = []
    for test_case in deduplicated:
        chromosome = tcc.TestCaseChromosome(test_case=test_case, test_factory=strategy.test_factory)
        for fitness_function in strategy.test_case_fitness_functions:
            chromosome.add_fitness_function(fitness_function)
        chromosomes.append(chromosome)
    merged_suite = strategy.create_test_suite(chromosomes)

    coverage_metrics = config.configuration.search_algorithm.coverage_metrics
    return generator.finalize_generation_result(
        strategy, executor, test_cluster, constant_provider, merged_suite, coverage_metrics
    )
