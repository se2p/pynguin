#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides factories for the generation algorithm."""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Callable, Generic, TypeVar

from ordered_set import OrderedSet

import pynguin.configuration as config
import pynguin.coverage.branchgoals as bg
import pynguin.ga.chromosome as chrom
import pynguin.ga.computations as ff
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.ga.testcasefactory as tcf
import pynguin.ga.testsuitechromosome as tsc
import pynguin.ga.testsuitechromosomefactory as tscf
import pynguin.generation.algorithms.archive as arch
import pynguin.generation.searchobserver as so
import pynguin.testcase.testfactory as tf
import pynguin.utils.statistics.statisticsobserver as sso
from pynguin.ga.operators.crossover.singlepointrelativecrossover import (
    SinglePointRelativeCrossOver,
)
from pynguin.ga.operators.ranking.rankingfunction import RankBasedPreferenceSorting
from pynguin.ga.operators.selection.rankselection import RankSelection
from pynguin.ga.operators.selection.selection import SelectionFunction
from pynguin.ga.operators.selection.tournamentselection import TournamentSelection
from pynguin.generation.algorithms.dynamosastrategy import DynaMOSATestStrategy
from pynguin.generation.algorithms.mioteststrategy import MIOTestStrategy
from pynguin.generation.algorithms.mosastrategy import MOSATestStrategy
from pynguin.generation.algorithms.randomsearchstrategy import (
    RandomTestCaseSearchStrategy,
    RandomTestSuiteSearchStrategy,
)
from pynguin.generation.algorithms.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.wholesuiteteststrategy import WholeSuiteTestStrategy
from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxIterationsStoppingCondition,
    MaxStatementExecutionsStoppingCondition,
    MaxTestExecutionsStoppingCondition,
    MaxTimeStoppingCondition,
)
from pynguin.setup.testcluster import FilteredTestCluster, TestCluster
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.exceptions import ConfigurationException

if TYPE_CHECKING:
    import pynguin.ga.chromosomefactory as cf
    from pynguin.ga.operators.crossover.crossover import CrossOverFunction
    from pynguin.ga.operators.ranking.rankingfunction import RankingFunction
    from pynguin.generation.algorithms.testgenerationstrategy import (
        TestGenerationStrategy,
    )
    from pynguin.generation.stoppingconditions.stoppingcondition import (
        StoppingCondition,
    )

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


class GenerationAlgorithmFactory(Generic[C], metaclass=ABCMeta):
    """A generic generation algorithm factory."""

    _logger = logging.getLogger(__name__)

    # pylint:disable=line-too-long
    _stopping_conditions: dict[
        config.StoppingCondition, Callable[[], StoppingCondition]
    ] = {
        config.StoppingCondition.MAX_ITERATIONS: MaxIterationsStoppingCondition,
        config.StoppingCondition.MAX_TEST_EXECUTIONS: MaxTestExecutionsStoppingCondition,
        config.StoppingCondition.MAX_STATEMENT_EXECUTIONS: MaxStatementExecutionsStoppingCondition,
        config.StoppingCondition.MAX_TIME: MaxTimeStoppingCondition,
    }

    def get_stopping_condition(self) -> StoppingCondition:
        """Instantiates the stopping condition depending on the configuration settings.

        Returns:
            A stopping condition
        """
        stopping_condition = config.configuration.stopping.stopping_condition
        self._logger.info("Using stopping condition: %s", stopping_condition)
        if stopping_condition in self._stopping_conditions:
            return self._stopping_conditions[stopping_condition]()
        self._logger.warning("Unknown stopping condition: %s", stopping_condition)
        return MaxTimeStoppingCondition()

    @abstractmethod
    def get_search_algorithm(self) -> TestGenerationStrategy:
        """Initialises and sets up the test-generation strategy to use.

        Returns:
            A fully configured test-generation strategy  # noqa: DAR202
        """


# pylint: disable=unsubscriptable-object, too-few-public-methods
class TestSuiteGenerationAlgorithmFactory(
    GenerationAlgorithmFactory[tsc.TestSuiteChromosome]
):
    """A factory for a search algorithm generating test-suites."""

    _strategies: dict[config.Algorithm, Callable[[], TestGenerationStrategy]] = {
        config.Algorithm.DYNAMOSA: DynaMOSATestStrategy,
        config.Algorithm.MIO: MIOTestStrategy,
        config.Algorithm.MOSA: MOSATestStrategy,
        config.Algorithm.RANDOM: RandomTestStrategy,
        config.Algorithm.RANDOM_TEST_SUITE_SEARCH: RandomTestSuiteSearchStrategy,
        config.Algorithm.RANDOM_TEST_CASE_SEARCH: RandomTestCaseSearchStrategy,
        config.Algorithm.WHOLE_SUITE: WholeSuiteTestStrategy,
    }

    _selections: dict[config.Selection, Callable[[], SelectionFunction]] = {
        config.Selection.TOURNAMENT_SELECTION: TournamentSelection,
        config.Selection.RANK_SELECTION: RankSelection,
    }

    def __init__(self, executor: TestCaseExecutor, test_cluster: TestCluster):
        self._executor = executor
        self._test_cluster = test_cluster

    def _get_chromosome_factory(
        self, strategy: TestGenerationStrategy
    ) -> cf.ChromosomeFactory:
        """Provides a chromosome factory.

        Args:
            strategy: The strategy that is currently configured.

        Returns:
            A chromosome factory
        """
        # TODO add conditional returns/other factories here
        test_case_factory: tcf.TestCaseFactory = tcf.RandomLengthTestCaseFactory(
            strategy.test_factory
        )
        if config.configuration.seeding.initial_population_seeding:
            self._logger.info("Using population seeding")
            test_case_factory = tcf.SeededTestCaseFactory(
                test_case_factory, strategy.test_factory
            )
        test_case_chromosome_factory: cf.ChromosomeFactory = (
            tccf.TestCaseChromosomeFactory(
                strategy.test_factory,
                test_case_factory,
                strategy.test_case_fitness_functions,
            )
        )
        if config.configuration.seeding.seed_from_archive:
            self._logger.info("Using archive seeding")
            test_case_chromosome_factory = tccf.ArchiveReuseTestCaseChromosomeFactory(
                test_case_chromosome_factory, strategy.archive
            )
        if config.configuration.algorithm in (
            config.Algorithm.DYNAMOSA,
            config.Algorithm.MIO,
            config.Algorithm.MOSA,
            config.Algorithm.RANDOM_TEST_CASE_SEARCH,
        ):
            return test_case_chromosome_factory
        return tscf.TestSuiteChromosomeFactory(
            test_case_chromosome_factory,
            strategy.test_suite_fitness_functions,
            strategy.test_suite_coverage_functions,
        )

    def get_search_algorithm(self) -> TestGenerationStrategy:
        """Initialises and sets up the test-generation strategy to use.

        Returns:
            A fully configured test-generation strategy
        """
        strategy = self._get_generation_strategy()
        strategy.branch_goal_pool = bg.BranchGoalPool(
            self._executor.tracer.get_known_data()
        )
        strategy.test_case_fitness_functions = self._get_test_case_fitness_functions(
            strategy
        )
        strategy.test_suite_fitness_functions = self._get_test_suite_fitness_functions()
        strategy.test_suite_coverage_functions = (
            self._get_test_suite_coverage_functions()
        )
        strategy.archive = self._get_archive(strategy)

        strategy.executor = self._executor
        strategy.test_cluster = self._get_test_cluster(strategy)
        strategy.test_factory = self._get_test_factory(strategy)
        chromosome_factory = self._get_chromosome_factory(strategy)
        strategy.chromosome_factory = chromosome_factory

        selection_function = self._get_selection_function()
        selection_function.maximize = False
        strategy.selection_function = selection_function

        stopping_condition = self.get_stopping_condition()
        strategy.stopping_condition = stopping_condition
        strategy.add_search_observer(stopping_condition)
        if stopping_condition.observes_execution:
            self._executor.add_observer(stopping_condition)
        strategy.add_search_observer(so.LogSearchObserver())
        strategy.add_search_observer(sso.SequenceStartTimeObserver())
        strategy.add_search_observer(sso.IterationObserver())
        strategy.add_search_observer(sso.BestIndividualObserver())

        crossover_function = self._get_crossover_function()
        strategy.crossover_function = crossover_function

        ranking_function = self._get_ranking_function()
        strategy.ranking_function = ranking_function

        return strategy

    @classmethod
    def _get_generation_strategy(cls) -> TestGenerationStrategy:
        """Provides a generation strategy.

        Returns:
            A generation strategy

        Raises:
            ConfigurationException: if an unknown algorithm was requested
        """
        if config.configuration.algorithm in cls._strategies:
            strategy = cls._strategies.get(config.configuration.algorithm)
            assert strategy, "Strategy cannot be defined as None"
            cls._logger.info("Using strategy: %s", config.configuration.algorithm)
            return strategy()
        raise ConfigurationException("No suitable generation strategy found.")

    @classmethod
    def _get_selection_function(cls) -> SelectionFunction[tsc.TestSuiteChromosome]:
        """Provides a selection function for the selected algorithm.

        Returns:
            A selection function

        Raises:
            ConfigurationException: if an unknown function was requested
        """
        if config.configuration.search_algorithm.selection in cls._selections:
            strategy = cls._selections.get(
                config.configuration.search_algorithm.selection
            )
            assert strategy, "Selection function cannot be defined as None"
            cls._logger.info(
                "Using selection function: %s",
                config.configuration.search_algorithm.selection,
            )
            return strategy()
        raise ConfigurationException("No suitable selection function found.")

    def _get_crossover_function(self) -> CrossOverFunction[tsc.TestSuiteChromosome]:
        """Provides a crossover function for the selected algorithm.

        Returns:
            A crossover function
        """
        self._logger.info("Using crossover function: SinglePointRelativeCrossOver")
        return SinglePointRelativeCrossOver()

    def _get_archive(self, strategy: TestGenerationStrategy) -> arch.Archive:
        if config.configuration.algorithm == config.Algorithm.MIO:
            self._logger.info("Using MIOArchive")
            size = config.configuration.mio.initial_config.number_of_tests_per_target
            return arch.MIOArchive(
                strategy.test_case_fitness_functions,
                initial_size=size,
            )
        # Use CoverageArchive as default, even if it the algorithm does not use it.
        self._logger.info("Using CoverageArchive")
        if config.configuration.algorithm == config.Algorithm.DYNAMOSA:
            # DynaMOSA gradually adds its fitness functions, so we initialize
            # with an empty set.
            return arch.CoverageArchive(OrderedSet())
        return arch.CoverageArchive(OrderedSet(strategy.test_case_fitness_functions))

    def _get_ranking_function(self) -> RankingFunction:
        self._logger.info("Using ranking function: RankBasedPreferenceSorting")
        return RankBasedPreferenceSorting()

    def _get_test_case_fitness_functions(
        self, strategy: TestGenerationStrategy
    ) -> OrderedSet[ff.TestCaseFitnessFunction]:
        """Creates the fitness functions for test cases.

        Args:
            strategy: The currently configured strategy

        Returns:
            A list of fitness functions
        """
        if config.configuration.algorithm in (
            config.Algorithm.DYNAMOSA,
            config.Algorithm.MIO,
            config.Algorithm.MOSA,
            config.Algorithm.RANDOM_TEST_CASE_SEARCH,
            config.Algorithm.WHOLE_SUITE,
        ):
            fitness_functions = OrderedSet()
            coverage_metrics = config.configuration.statistics_output.coverage_metrics
            if config.CoverageMetric.LINE in coverage_metrics:
                fitness_functions.update(
                    bg.create_line_coverage_fitness_functions(self._executor)
                )

            if config.CoverageMetric.BRANCH in coverage_metrics:
                fitness_functions.update(
                    bg.create_branch_coverage_fitness_functions(
                        self._executor, strategy.branch_goal_pool
                    )
                )
            self._logger.info(
                "Instantiated %d fitness functions", len(fitness_functions)
            )
            return fitness_functions
        return OrderedSet()

    def _get_test_suite_fitness_functions(
        self,
    ) -> OrderedSet[ff.TestSuiteFitnessFunction]:
        test_suite_ffs = OrderedSet()
        coverage_metrics = config.configuration.statistics_output.coverage_metrics
        if config.CoverageMetric.LINE in coverage_metrics:
            test_suite_ffs.update([ff.LineTestSuiteFitnessFunction(self._executor)])
        if config.CoverageMetric.BRANCH in coverage_metrics:
            test_suite_ffs.update(
                [ff.BranchDistanceTestSuiteFitnessFunction(self._executor)]
            )
        return test_suite_ffs

    def _get_test_suite_coverage_functions(
        self,
    ) -> OrderedSet[ff.TestSuiteCoverageFunction]:
        test_suite_ffs = OrderedSet()
        coverage_metrics = config.configuration.statistics_output.coverage_metrics
        if config.CoverageMetric.LINE in coverage_metrics:
            test_suite_ffs.update([ff.TestSuiteLineCoverageFunction(self._executor)])
        if config.CoverageMetric.BRANCH in coverage_metrics:
            test_suite_ffs.update([ff.TestSuiteBranchCoverageFunction(self._executor)])
        return test_suite_ffs

    def _get_test_cluster(self, strategy: TestGenerationStrategy):
        search_alg = config.configuration.search_algorithm
        if search_alg.filter_covered_targets_from_test_cluster:
            # Wrap test cluster in filter.
            return FilteredTestCluster(
                self._test_cluster,
                strategy.archive,
                self._executor.tracer.get_known_data(),
                strategy.test_case_fitness_functions,
            )
        return self._test_cluster

    @staticmethod
    def _get_test_factory(strategy: TestGenerationStrategy):
        return tf.TestFactory(strategy.test_cluster)
