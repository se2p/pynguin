#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Pynguin is an automated unit test generation framework for Python.

The framework generates unit tests for a given Python module.  For this it
supports various approaches, such as a random approach, similar to Randoop or a
whole-suite approach, based on a genetic algorithm, as implemented in EvoSuite.  The
framework allows to export test suites in various styles, i.e., using the `unittest`
library from the Python standard library or tests in the style used by the PyTest
framework.

Pynguin is supposed to be used as a standalone command-line application but it
can also be used as a library by instantiating this class directly.
"""
import enum
import importlib
import logging
import os
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple

import pynguin.assertion.assertiongenerator as ag
import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.chromosomeconverter as cc
import pynguin.ga.postprocess as pp
import pynguin.testcase.testcase as tc
from pynguin.analyses.duckmock.duckmockanalysis import DuckMockAnalysis
from pynguin.analyses.seeding.staticconstantseeding import StaticConstantSeeding
from pynguin.generation.algorithms.randomsearch.randomsearchstrategy import (
    RandomSearchStrategy,
)
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.algorithms.wspy.wholesuiteteststrategy import (
    WholeSuiteTestStrategy,
)
from pynguin.generation.export.exportprovider import ExportProvider
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.setup.testcluster import TestCluster
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker
from pynguin.utils.statistics.timer import Timer


@enum.unique
class ReturnCode(enum.IntEnum):
    """Return codes for Pynguin to signal result."""

    OK = 0
    """Symbolises that the execution ended as expected."""

    SETUP_FAILED = 1
    """Symbolises that the execution failed in the setup phase."""

    NO_TESTS_GENERATED = 2
    """Symbolises that no test could be generated."""


# pylint: disable=too-few-public-methods
class Pynguin:
    """Pynguin is an automated unit test generation framework for Python.

    The framework generates unit tests for a given Python module.  For this it
    supports various approaches, such as a random approach, similar to Randoop or a
    whole-suite approach, based on a genetic algorithm.  The framework allows to
    export test suites in various styles, i.e., using the `unittest` library from the
    Python standard library or tests in the style used by the PyTest framework.

    Pynguin is supposed to be used as a standalone command-line application but it
    can also be used as a library by instantiating this class directly.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self, configuration: config.Configuration) -> None:
        """Initialises the test generator with the given configuration.

        Args:
            configuration: The configuration to use.
        """
        config.INSTANCE = configuration

    def run(self) -> ReturnCode:
        """Run the test generation.

        The result of the test generation is indicated by the resulting ReturnCode.

        Returns:
            See ReturnCode.

        Raises:
            ConfigurationException: In case the configuration is illegal
        """
        try:
            self._logger.info("Start Pynguin Test Generation…")
            return self._run()
        finally:
            self._logger.info("Stop Pynguin Test Generation…")

    def _setup_test_cluster(self) -> Optional[TestCluster]:
        with Timer(name="Test-cluster generation time", logger=None):
            test_cluster = TestClusterGenerator(
                config.INSTANCE.module_name
            ).generate_cluster()
            if test_cluster.num_accessible_objects_under_test() == 0:
                self._logger.error("SUT contains nothing we can test.")
                return None
            return test_cluster

    def _setup_path(self) -> bool:
        """Inserts the path to the SUT into the path list, installs the import hook and
        tries to load the SUT.

        Returns:
            An optional execution tracer, if loading was successful, None otherwise.
        """
        if not os.path.isdir(config.INSTANCE.project_path):
            self._logger.error(
                "%s is not a valid project path", config.INSTANCE.project_path
            )
            return False
        self._logger.debug("Setting up path for %s", config.INSTANCE.project_path)
        sys.path.insert(0, config.INSTANCE.project_path)
        return True

    def _setup_import_hook(self) -> ExecutionTracer:
        self._logger.debug(
            "Setting up instrumentation for %s", config.INSTANCE.module_name
        )
        tracer = ExecutionTracer()
        install_import_hook(config.INSTANCE.module_name, tracer)
        return tracer

    def _load_sut(self) -> bool:
        try:
            importlib.import_module(config.INSTANCE.module_name)
        except ImportError as ex:
            # A module could not be imported because some dependencies
            # are missing or it is malformed
            self._logger.error("Failed to load SUT: %s", ex)
            return False
        return True

    def _setup_random_number_generator(self) -> None:
        """Setup RNG."""
        if config.INSTANCE.seed is None:
            self._logger.info("No seed given. Using %d", randomness.RNG.get_seed())
        else:
            self._logger.info("Using seed %d", config.INSTANCE.seed)
            randomness.RNG.seed(config.INSTANCE.seed)

    def _setup_constant_seeding_collection(self) -> None:
        """Collect constants from SUT, if enabled."""
        if config.INSTANCE.constant_seeding:
            self._logger.info("Collecting constants from SUT.")
            StaticConstantSeeding().collect_constants(config.INSTANCE.project_path)

    def _setup_type_analysis(
        self, test_cluster: TestCluster
    ) -> Optional[DuckMockAnalysis]:
        if config.INSTANCE.duck_type_analysis:
            self._logger.info("Analysing classes and methods in SUT.")
            analysis = DuckMockAnalysis(config.INSTANCE.module_name)
            analysis.analyse()
            analysis.update_test_cluster(test_cluster)
            return analysis
        return None

    def _setup_and_check(self) -> Optional[Tuple[TestCaseExecutor, TestCluster]]:
        """Load the System Under Test (SUT) i.e. the module that is tested.

        Perform setup and some sanity checks.

        Returns:
            An optional tuple of test-case executor and test cluster
        """

        if not self._setup_path():
            return None
        tracer = self._setup_import_hook()
        if not self._load_sut():
            return None
        if (test_cluster := self._setup_test_cluster()) is None:
            return None
        executor = TestCaseExecutor(tracer)
        self._track_sut_data(tracer, test_cluster)
        self._setup_random_number_generator()
        self._setup_constant_seeding_collection()
        if (type_analysis := self._setup_type_analysis(test_cluster)) is not None:
            self._export_type_analysis_results(type_analysis)
        return executor, test_cluster

    @staticmethod
    def _track_sut_data(tracer: ExecutionTracer, test_cluster: TestCluster) -> None:
        """Track data from the SUT.

        Args:
            tracer: the execution tracer
            test_cluster: the test cluster
        """
        tracker = StatisticsTracker()
        tracker.track_output_variable(
            RuntimeVariable.CodeObjects,
            len(tracer.get_known_data().existing_code_objects),
        )
        tracker.track_output_variable(
            RuntimeVariable.Predicates, len(tracer.get_known_data().existing_predicates)
        )
        tracker.track_output_variable(
            RuntimeVariable.AccessibleObjectsUnderTest,
            test_cluster.num_accessible_objects_under_test(),
        )
        tracker.track_output_variable(
            RuntimeVariable.GeneratableTypes,
            len(test_cluster.get_all_generatable_types()),
        )

    def _run(self) -> ReturnCode:
        if (setup_result := self._setup_and_check()) is None:
            return ReturnCode.SETUP_FAILED
        executor, test_cluster = setup_result

        with Timer(name="Test generation time", logger=None):
            algorithm: TestGenerationStrategy = (
                self._instantiate_test_generation_strategy(executor, test_cluster)
            )
            self._logger.info(
                "Start generating sequences using %s", config.INSTANCE.algorithm
            )
            StatisticsTracker().set_sequence_start_time(time.time_ns())
            generation_result = algorithm.generate_tests()
            self._logger.info(
                "Stop generating sequences using %s", config.INSTANCE.algorithm
            )
            algorithm.send_statistics()

            with Timer(name="Re-execution time", logger=None):
                StatisticsTracker().track_output_variable(
                    RuntimeVariable.Coverage, generation_result.get_coverage()
                )

            if config.INSTANCE.post_process:
                postprocessor = pp.ExceptionTruncation()
                generation_result.accept(postprocessor)
                # TODO(fk) add more postprocessing stuff.

            if config.INSTANCE.generate_assertions:
                generator = ag.AssertionGenerator(executor)
                generation_result.accept(generator)

            with Timer(name="Export time", logger=None):
                converter = cc.ChromosomeConverter()
                generation_result.accept(converter)
                failing = converter.failing_test_suite
                passing = converter.passing_test_suite
                written_to = self._export_test_cases(
                    [t.test_case for t in passing.test_case_chromosomes]
                )
                self._logger.info(
                    "Export %i successful test cases to %s",
                    passing.size(),
                    written_to,
                )
                written_to = self._export_test_cases(
                    [t.test_case for t in failing.test_case_chromosomes],
                    "_failing",
                    wrap_code=True,
                )
                self._logger.info(
                    "Export %i failing test cases to %s", failing.size(), written_to
                )

        self._track_statistics(passing, failing, generation_result)
        self._collect_statistics()
        if not StatisticsTracker().write_statistics():
            self._logger.error("Failed to write statistics data")
        if generation_result.size() == 0:
            # not able to generate one test case
            return ReturnCode.NO_TESTS_GENERATED
        return ReturnCode.OK

    _strategies: Dict[
        config.Algorithm,
        Callable[[TestCaseExecutor, TestCluster], TestGenerationStrategy],
    ] = {
        config.Algorithm.RANDOOPY: RandomTestStrategy,
        config.Algorithm.RANDOMSEARCH: RandomSearchStrategy,
        config.Algorithm.WSPY: WholeSuiteTestStrategy,
    }

    @classmethod
    def _instantiate_test_generation_strategy(
        cls, executor: TestCaseExecutor, test_cluster: TestCluster
    ) -> TestGenerationStrategy:
        if config.INSTANCE.algorithm in cls._strategies:
            strategy = cls._strategies.get(config.INSTANCE.algorithm)
            assert strategy, "Strategy cannot be defined as None"
            return strategy(executor, test_cluster)
        raise ConfigurationException("Unknown algorithm selected")

    @staticmethod
    def _collect_statistics() -> None:
        tracker = StatisticsTracker()
        tracker.track_output_variable(
            RuntimeVariable.TargetModule, config.INSTANCE.module_name
        )
        tracker.track_output_variable(
            RuntimeVariable.RandomSeed, randomness.RNG.get_seed()
        )
        tracker.track_output_variable(
            RuntimeVariable.ConfigurationId, config.INSTANCE.configuration_id
        )
        for runtime_variable, value in tracker.variables_generator:
            tracker.set_output_variable_for_runtime_variable(runtime_variable, value)

    @staticmethod
    def _track_statistics(
        passing: chrom.Chromosome,
        failing: chrom.Chromosome,
        result: chrom.Chromosome,
    ) -> None:
        tracker = StatisticsTracker()
        tracker.current_individual(result)
        tracker.track_output_variable(RuntimeVariable.Size, result.size())
        tracker.track_output_variable(RuntimeVariable.Length, result.length())
        tracker.track_output_variable(RuntimeVariable.FailingSize, failing.size())
        tracker.track_output_variable(
            RuntimeVariable.FailingLength,
            failing.length(),
        )
        tracker.track_output_variable(RuntimeVariable.PassingSize, passing.size())
        tracker.track_output_variable(RuntimeVariable.PassingLength, passing.length())

    @staticmethod
    def _export_test_cases(
        test_cases: List[tc.TestCase], suffix: str = "", wrap_code: bool = False
    ) -> str:
        """Export the given test cases.

        Args:
            test_cases: A list of test cases to export
            suffix: Suffix that can be added to the file name to distinguish
                between different results e.g., failing and succeeding test cases.
            wrap_code: Whether or not the generated code shall be wrapped

        Returns:
            The name of the target file
        """
        exporter = ExportProvider.get_exporter(wrap_code=wrap_code)
        target_file = os.path.join(
            config.INSTANCE.output_path,
            "test_" + config.INSTANCE.module_name.replace(".", "_") + suffix + ".py",
        )
        exporter.export_sequences(target_file, test_cases)
        return target_file

    @staticmethod
    def _export_type_analysis_results(type_analysis: DuckMockAnalysis):
        pass
