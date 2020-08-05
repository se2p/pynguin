# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
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
import logging
import os
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.analyses.seeding.staticconstantseeding import StaticConstantSeeding
from pynguin.generation.algorithms.randoopy.randomtestmonkeytypestrategy import (
    RandomTestMonkeyTypeStrategy,
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
class ReturnCodes(enum.IntEnum):
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
        """Initialises the test generator.

        The generator needs a configuration. If none is present, the generator
        cannot be initialised and will thus raise a `ConfigurationException`.

        Args:
            configuration: An optional pre-generated configuration.

        Raises:
            ConfigurationException: In case there is no proper configuration
        """
        if configuration is None:
            raise ConfigurationException(
                "Cannot initialise test generator without proper configuration."
            )
        config.INSTANCE = configuration

    def run(self) -> int:
        """Run the test generation.

        This method behaves like a standard UNIX command-line application, i.e.,
        the return value `0` signals a successful execution.  Any other return value
        signals some errors.  This is, e.g., the case if the framework was not able
        to generate one successfully running test case for the class under test.

        Returns:
            See ReturnCodes.

        Raises:
            ConfigurationException: In case the configuration is illegal
        """
        try:
            self._logger.info("Start Pynguin Test Generation…")
            return self._run()
        finally:
            self._logger.info("Stop Pynguin Test Generation…")

    def _setup_executor(self, tracer: ExecutionTracer) -> Optional[TestCaseExecutor]:
        try:
            executor = TestCaseExecutor(tracer)
        except ImportError as ex:
            # A module could not be imported because some dependencies
            # are missing or it is malformed
            self._logger.error("Failed to load SUT: %s", ex)
            return None
        return executor

    def _setup_test_cluster(self) -> Optional[TestCluster]:
        with Timer(name="Test-cluster generation time", logger=None):
            test_cluster = TestClusterGenerator(
                config.INSTANCE.module_name
            ).generate_cluster()
            if test_cluster.num_accessible_objects_under_test() == 0:
                self._logger.error("SUT contains nothing we can test.")
                return None
            return test_cluster

    def _setup_path_and_hook(self) -> Optional[ExecutionTracer]:
        """Inserts the path to the SUT into the path list.

        Also installs the import hook.

        Returns:
            An optional execution tracer
        """
        if not os.path.isdir(config.INSTANCE.project_path):
            self._logger.error(
                "%s is not a valid project path", config.INSTANCE.project_path
            )
            return None
        self._logger.debug("Setting up path for %s", config.INSTANCE.project_path)
        sys.path.insert(0, config.INSTANCE.project_path)
        self._logger.debug(
            "Setting up instrumentation for %s", config.INSTANCE.module_name
        )
        tracer = ExecutionTracer()
        install_import_hook(config.INSTANCE.module_name, tracer)
        return tracer

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

    def _setup_and_check(self) -> Optional[Tuple[TestCaseExecutor, TestCluster]]:
        """Load the System Under Test (SUT) i.e. the module that is tested.

        Perform setup and some sanity checks.

        Returns:
            An optional tuple of test-case executor and test cluster
        """
        if (tracer := self._setup_path_and_hook()) is None:
            return None
        if (executor := self._setup_executor(tracer)) is None:
            return None
        if (test_cluster := self._setup_test_cluster()) is None:
            return None
        self._track_sut_data(tracer, test_cluster)
        self._setup_random_number_generator()
        self._setup_constant_seeding_collection()
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

    def _run(self) -> int:
        status = ReturnCodes.OK.value

        if (setup_result := self._setup_and_check()) is None:
            return ReturnCodes.SETUP_FAILED.value
        executor, test_cluster = setup_result

        with Timer(name="Test generation time", logger=None):
            algorithm: TestGenerationStrategy = self._instantiate_test_generation_strategy(
                executor, test_cluster
            )
            self._logger.info(
                "Start generating sequences using %s", config.INSTANCE.algorithm
            )
            StatisticsTracker().set_sequence_start_time(time.time_ns())
            non_failing, failing = algorithm.generate_sequences()
            self._logger.info(
                "Stop generating sequences using %s", config.INSTANCE.algorithm
            )
            algorithm.send_statistics()

            with Timer(name="Re-execution time", logger=None):
                combined = tsc.TestSuiteChromosome()
                for fitness_func in non_failing.get_fitness_functions():
                    combined.add_fitness_function(fitness_func)
                combined.add_tests(non_failing.test_chromosomes)
                combined.add_tests(failing.test_chromosomes)
                StatisticsTracker().track_output_variable(
                    RuntimeVariable.Coverage, combined.get_coverage()
                )

            with Timer(name="Export time", logger=None):
                written_to = self._export_test_cases(non_failing.test_chromosomes)
                self._logger.info(
                    "Export %i successful test cases to %s",
                    non_failing.size(),
                    written_to,
                )
                written_to = self._export_test_cases(
                    failing.test_chromosomes, "_failing", wrap_code=True
                )
                self._logger.info(
                    "Export %i failing test cases to %s", failing.size(), written_to
                )

        self._track_statistics(non_failing, failing, combined)
        self._collect_statistics()
        if not StatisticsTracker().write_statistics():
            self._logger.error("Failed to write statistics data")
        if combined.size == 0:
            # not able to generate one test case
            return ReturnCodes.NO_TESTS_GENERATED.value
        return status

    _strategies: Dict[
        config.Algorithm,
        Callable[[TestCaseExecutor, TestCluster], TestGenerationStrategy],
    ] = {
        config.Algorithm.RANDOOPY: RandomTestStrategy,
        config.Algorithm.RANDOOPY_MONKEYTYPE: RandomTestMonkeyTypeStrategy,
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
        non_failing: tsc.TestSuiteChromosome,
        failing: tsc.TestSuiteChromosome,
        combined: tsc.TestSuiteChromosome,
    ) -> None:
        tracker = StatisticsTracker()
        tracker.current_individual(combined)
        tracker.track_output_variable(RuntimeVariable.Size, combined.size())
        tracker.track_output_variable(
            RuntimeVariable.Length, combined.total_length_of_test_cases
        )
        tracker.track_output_variable(RuntimeVariable.FailingSize, failing.size())
        tracker.track_output_variable(
            RuntimeVariable.FailingLength, failing.total_length_of_test_cases,
        )
        tracker.track_output_variable(RuntimeVariable.PassingSize, non_failing.size())
        tracker.track_output_variable(
            RuntimeVariable.PassingLength, non_failing.total_length_of_test_cases
        )

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
