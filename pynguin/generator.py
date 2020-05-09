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
import argparse
import enum
import logging
import os
import sys
from typing import Union, List, Dict, Callable, Tuple, Optional

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
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.statistics.statistics import StatisticsTracker, RuntimeVariable
from pynguin.utils.statistics.timer import Timer


@enum.unique
class ReturnCodes(enum.IntEnum):
    """Return codes for Pynguin to signal result."""

    OK = 0
    SETUP_FAILED = 1
    NO_TESTS_GENERATED = 2


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

    def __init__(
        self,
        argument_parser: argparse.ArgumentParser = None,
        arguments: List[str] = None,
        configuration: config.Configuration = None,
        verbosity: int = -1,
    ) -> None:
        """Initialises the test generator.

        The generator needs a configuration, which can either be provided via the
        `configuration` parameter or via an argument parser and a list of
        command-line arguments.  If none of these is present, the generator cannot be
        initialised and will thus raise a `ConfigurationException`.

        :param argument_parser: An optional argument parser.
        :param arguments: An optional list of command-line arguments.
        :param configuration: An optional pre-generated configuration.
        :raises ConfigurationException: In case there is no proper configuration
        """
        if configuration:
            config.INSTANCE = configuration
        elif argument_parser and arguments:
            parsed = argument_parser.parse_args(arguments)
            config.INSTANCE = parsed.config
            verbosity = parsed.verbosity
        else:
            raise ConfigurationException(
                "Cannot initialise test generator without proper configuration."
            )
        self._logger = self._setup_logging(verbosity, config.INSTANCE.log_file)

    def run(self) -> int:
        """Run the test generation.

        This method behaves like a standard UNIX command-line application, i.e.,
        the return value `0` signals a successful execution.  Any other return value
        signals some errors.  This is, e.g., the case if the framework was not able
        to generate one successfully running test case for the class under test.

        :return: See ReturnCodes.
        """
        if not self._logger:
            raise ConfigurationException()

        try:
            self._logger.info("Start Pynguin Test Generation…")
            return self._run()
        finally:
            self._logger.info("Stop Pynguin Test Generation…")

    def _setup_executor(self) -> Optional[TestCaseExecutor]:
        try:
            executor = TestCaseExecutor()
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

    def _setup_path_and_hook(self) -> bool:
        """Inserts the path to the SUT into the path list.
        Also installs the import hook."""
        if not os.path.isdir(config.INSTANCE.project_path):
            self._logger.error(
                "%s is not a valid project path", config.INSTANCE.project_path
            )
            return False
        self._logger.debug("Setting up path for %s", config.INSTANCE.project_path)
        sys.path.insert(0, config.INSTANCE.project_path)
        self._logger.debug(
            "Setting up instrumentation for %s", config.INSTANCE.project_path
        )
        install_import_hook(config.INSTANCE.module_name)
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

    def _setup_and_check(self) -> Optional[Tuple[TestCaseExecutor, TestCluster]]:
        """Load the System Under Test (SUT) i.e. the module that is tested.
        Perform setup and some sanity checks."""
        if not self._setup_path_and_hook():
            return None
        if (executor := self._setup_executor()) is None:
            return None
        if (test_cluster := self._setup_test_cluster()) is None:
            return None
        self._setup_random_number_generator()
        self._setup_constant_seeding_collection()
        return executor, test_cluster

    def _run(self) -> int:
        status = ReturnCodes.OK.value

        if (setup_result := self._setup_and_check()) is None:
            return ReturnCodes.SETUP_FAILED.value
        executor, test_cluster = setup_result

        with Timer(name="Test generation time", logger=None):
            algorithm: TestGenerationStrategy = self._instantiate_test_generation_strategy(
                executor, test_cluster
            )
            non_failing, failing = algorithm.generate_sequences()
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
                self._logger.info("Export successful test cases")
                self._export_test_cases(non_failing.test_chromosomes)
                self._logger.info("Export failing test cases")
                self._export_test_cases(
                    failing.test_chromosomes, "_failing", wrap_code=True
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
            RuntimeVariable.Random_Seed, randomness.RNG.get_seed()
        )
        tracker.track_output_variable(
            RuntimeVariable.configuration_id, config.INSTANCE.configuration_id
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
    ) -> None:
        """Export the given test cases.

        :param test_cases: A list of test cases to export
        :param suffix: Suffix that can be added to the file name to distinguish
            between different results e.g., failing and succeeding test cases.
        :param wrap_code: Whether or not the generated code shall be wrapped
        """
        exporter = ExportProvider.get_exporter(wrap_code=wrap_code)
        target_file = os.path.join(
            config.INSTANCE.output_path,
            "test_" + config.INSTANCE.module_name.replace(".", "_") + suffix + ".py",
        )
        exporter.export_sequences(target_file, test_cases)

    @staticmethod
    def _setup_logging(
        verbosity: int, log_file: Union[str, os.PathLike] = None,
    ) -> logging.Logger:
        logger = logging.getLogger("pynguin")
        logger.setLevel(logging.DEBUG)

        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)s](%(name)s:%(funcName)s:%(lineno)d: "
                    "%(message)s"
                )
            )
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)

        if verbosity < 0:
            logger.addHandler(logging.NullHandler())
        else:
            level = logging.WARNING
            if verbosity == 1:
                level = logging.INFO
            if verbosity >= 2:
                level = logging.DEBUG

            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(
                logging.Formatter("[%(levelname)s](%(name)s): %(message)s")
            )
            logger.addHandler(console_handler)

        return logger
