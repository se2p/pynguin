#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides factories for the generation algorithm."""
import logging
from abc import ABCMeta, abstractmethod
from typing import Callable, Dict, Generic, List, TypeVar

import pynguin.configuration as config
import pynguin.coverage.branch.branchcoveragefactory as bcf
import pynguin.ga.chromosome as chrom
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.branchdistancetestsuitefitness as bdtsf
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.ga.testcasefactory as tcf
import pynguin.ga.testsuitechromosome as tsc
import pynguin.ga.testsuitechromosomefactory as tscf
import pynguin.testcase.testfactory as tf
from pynguin.ga.operators.crossover.crossover import CrossOverFunction
from pynguin.ga.operators.crossover.singlepointrelativecrossover import (
    SinglePointRelativeCrossOver,
)
from pynguin.ga.operators.ranking.rankingfunction import (
    RankBasedPreferenceSorting,
    RankingFunction,
)
from pynguin.ga.operators.selection.rankselection import RankSelection
from pynguin.ga.operators.selection.selection import SelectionFunction
from pynguin.generation.algorithms.dynamosastrategy import DynaMOSATestStrategy
from pynguin.generation.algorithms.mioteststrategy import MIOTestStrategy
from pynguin.generation.algorithms.mosastrategy import MOSATestStrategy
from pynguin.generation.algorithms.randomsearchstrategy import (
    RandomTestCaseSearchStrategy,
    RandomTestSuiteSearchStrategy,
)
from pynguin.generation.algorithms.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.algorithms.wholesuiteteststrategy import WholeSuiteTestStrategy
from pynguin.generation.algorithms.wraptestsuitemixin import WrapTestSuiteMixin
from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxIterationsStoppingCondition,
    MaxTestsStoppingCondition,
    MaxTimeStoppingCondition,
    StoppingCondition,
)
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils.exceptions import ConfigurationException

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


class GenerationAlgorithmFactory(Generic[C], metaclass=ABCMeta):
    """A generic generation algorithm factory."""

    _logger = logging.getLogger(__name__)

    def get_stopping_condition(self) -> StoppingCondition:
        """Instantiates the stopping condition depending on the configuration settings.

        Returns:
            A stopping condition
        """
        stopping_condition = config.configuration.stopping_condition
        self._logger.info("Setting stopping condition: %s", stopping_condition)
        if stopping_condition == config.StoppingCondition.MAX_ITERATIONS:
            return MaxIterationsStoppingCondition()
        if stopping_condition == config.StoppingCondition.MAX_TESTS:
            return MaxTestsStoppingCondition()
        if stopping_condition == config.StoppingCondition.MAX_TIME:
            return MaxTimeStoppingCondition()
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

    _strategies: Dict[config.Algorithm, Callable[[], TestGenerationStrategy]] = {
        config.Algorithm.DYNAMOSA: DynaMOSATestStrategy,
        config.Algorithm.MIO: MIOTestStrategy,
        config.Algorithm.MOSA: MOSATestStrategy,
        config.Algorithm.RANDOM: RandomTestStrategy,
        config.Algorithm.RANDOM_TEST_SUITE_SEARCH: RandomTestSuiteSearchStrategy,
        config.Algorithm.RANDOM_TEST_CASE_SEARCH: RandomTestCaseSearchStrategy,
        config.Algorithm.WHOLE_SUITE: WholeSuiteTestStrategy,
    }

    def __init__(self, executor: TestCaseExecutor, test_cluster: TestCluster):
        self._executor = executor
        self._test_cluster = test_cluster
        self._test_factory = tf.TestFactory(self._test_cluster)

    def _get_chromosome_factory(self) -> cf.ChromosomeFactory:
        """Provides a chromosome factory.

        Returns:
            A chromosome factory
        """
        # TODO add conditional returns/other factories here
        test_case_factory: tcf.TestCaseFactory = tcf.RandomLengthTestCaseFactory(
            self._test_factory
        )
        if config.configuration.initial_population_seeding:
            test_case_factory = tcf.SeededTestCaseFactory(
                test_case_factory, self._test_factory
            )
        test_case_chromosome_factory = tccf.TestCaseChromosomeFactory(
            self._test_factory, test_case_factory
        )
        if config.configuration.algorithm in (
            config.Algorithm.DYNAMOSA,
            config.Algorithm.MIO,
            config.Algorithm.MOSA,
            config.Algorithm.RANDOM_TEST_CASE_SEARCH,
        ):
            return test_case_chromosome_factory
        return tscf.TestSuiteChromosomeFactory(test_case_chromosome_factory)

    def get_search_algorithm(self) -> TestGenerationStrategy:
        """Initialises and sets up the test-generation strategy to use.

        Returns:
            A fully configured test-generation strategy
        """
        chromosome_factory = self._get_chromosome_factory()
        strategy = self._get_generation_strategy()

        strategy.chromosome_factory = chromosome_factory
        strategy.executor = self._executor
        strategy.test_cluster = self._test_cluster
        strategy.test_factory = self._test_factory

        fitness_functions = self._get_fitness_functions()
        strategy.fitness_functions = fitness_functions

        if isinstance(strategy, WrapTestSuiteMixin):
            test_suite_fitness_function = self._get_test_suite_fitness_function()
            strategy.test_suite_fitness_function = test_suite_fitness_function

        selection_function = self._get_selection_function()
        selection_function.maximize = False
        strategy.selection_function = selection_function

        stopping_condition = self.get_stopping_condition()
        strategy.stopping_condition = stopping_condition
        strategy.reset_stopping_conditions()

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
            return strategy()
        raise ConfigurationException("No suitable generation strategy found.")

    def _get_selection_function(self) -> SelectionFunction[tsc.TestSuiteChromosome]:
        """Provides a selection function for the selected algorithm.

        Returns:
            A selection function
        """
        self._logger.info("Chosen selection function: RankSelection")
        return RankSelection()

    def _get_crossover_function(self) -> CrossOverFunction[tsc.TestSuiteChromosome]:
        """Provides a crossover function for the selected algorithm.

        Returns:
            A crossover function
        """
        self._logger.info("Chosen crossover function: SinglePointRelativeCrossOver()")
        return SinglePointRelativeCrossOver()

    def _get_ranking_function(self) -> RankingFunction:
        self._logger.info("Chosen ranking function: RankBasedPreferenceSorting")
        return RankBasedPreferenceSorting()

    def _get_fitness_functions(self) -> List[ff.FitnessFunction]:
        """Converts a criterion into a test suite fitness function.

        Returns:
            A list of fitness functions
        """
        if config.configuration.algorithm in (
            config.Algorithm.DYNAMOSA,
            config.Algorithm.MIO,
            config.Algorithm.MOSA,
            config.Algorithm.RANDOM_TEST_CASE_SEARCH,
        ):
            factory = bcf.BranchCoverageFactory(self._executor)
            fitness_functions: List[ff.FitnessFunction] = factory.get_coverage_goals()
            self._logger.info(
                "Instantiated %d fitness functions", len(fitness_functions)
            )
            return fitness_functions
        return [self._get_test_suite_fitness_function()]

    def _get_test_suite_fitness_function(self) -> ff.FitnessFunction:
        return bdtsf.BranchDistanceTestSuiteFitnessFunction(self._executor)
