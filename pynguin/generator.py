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
import logging
import os
import sys
from typing import Union, List, Dict, Any, Callable

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
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
from pynguin.testcase.execution.abstractexecutor import AbstractExecutor
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.statistics.statistics import StatisticsTracker, RuntimeVariable
from pynguin.utils.statistics.timer import Timer


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
        if config.INSTANCE.configuration_id:
            StatisticsTracker().track_output_variable(
                RuntimeVariable.configuration_id, config.INSTANCE.configuration_id
            )

    def run(self) -> int:
        """Run the test generation.

        This method behaves like a standard UNIX command-line application, i.e.,
        the return value `0` signals a successful execution.  Any other return value
        signals some errors.  This is, e.g., the case if the framework was not able
        to generate one successfully running test case for the class under test.

        :return: 0 if the generation was successful, other values otherwise.
        """
        if not self._logger:
            raise ConfigurationException()

        try:
            self._logger.info("Start Pynguin Test Generation…")
            return self._run()
        finally:
            self._logger.info("Stop Pynguin Test Generation…")

    def _run(self) -> int:
        status = 0

        sys.path.insert(0, config.INSTANCE.project_path)
        if config.INSTANCE.seed is not None:
            randomness.RNG.seed(config.INSTANCE.seed)

        with install_import_hook(
            config.INSTANCE.algorithm.use_instrumentation, config.INSTANCE.module_name
        ):
            try:
                executor = TestCaseExecutor()
            except ModuleNotFoundError:
                # A module could not be imported because some dependencies are missing.
                # Thus we are not able to generate anything.  Stop the process here,
                # and write statistics.
                StatisticsTracker().current_individual(tsc.TestSuiteChromosome())
                StatisticsTracker().track_output_variable(
                    RuntimeVariable.TARGET_CLASS, config.INSTANCE.module_name
                )
                self._collect_statistics()
                StatisticsTracker().write_statistics()
                return 1

            with Timer(name="Test-cluster generation time", logger=None):
                test_cluster = TestClusterGenerator(
                    config.INSTANCE.module_name
                ).generate_cluster()

            timer = Timer(name="Test generation time", logger=None)
            timer.start()
            algorithm: TestGenerationStrategy = self._instantiate_test_generation_strategy(
                executor, test_cluster
            )
            test_chromosome, failing_test_chromosome = algorithm.generate_sequences()
            algorithm.send_statistics()

            with Timer(name="Re-execution time", logger=None):
                test_suite = tsc.TestSuiteChromosome()
                test_suite.add_tests(test_chromosome.test_chromosomes)
                test_suite.add_tests(failing_test_chromosome.test_chromosomes)
                re_executor = TestCaseExecutor()
                result = re_executor.execute_test_suite(test_suite)

            export_timer = Timer(name="Export time", logger=None)
            export_timer.start()
            self._logger.info("Export successful test cases")
            self._export_test_cases(test_chromosome.test_chromosomes)
            self._logger.info("Export failing test cases")
            self._export_test_cases(
                failing_test_chromosome.test_chromosomes, "_failing"
            )
            export_timer.stop()
            self._track_statistics(result, test_chromosome, failing_test_chromosome)
            timer.stop()
            self._collect_statistics()
            if not StatisticsTracker().write_statistics():
                self._logger.error("Failed to write statistics data")
            if test_chromosome.size == 0:
                # not able to generate one successful test case
                status = 1

        return status

    _strategies: Dict[
        config.Algorithm,
        Callable[[AbstractExecutor, TestCluster], TestGenerationStrategy],
    ] = {
        config.Algorithm.RANDOOPY: RandomTestStrategy,
        config.Algorithm.RANDOOPY_MONKEYTYPE: RandomTestMonkeyTypeStrategy,
        config.Algorithm.WSPY: WholeSuiteTestStrategy,
    }

    @classmethod
    def _instantiate_test_generation_strategy(
        cls, executor: AbstractExecutor, test_cluster: TestCluster
    ) -> TestGenerationStrategy:
        if config.INSTANCE.algorithm in cls._strategies:
            strategy = cls._strategies.get(config.INSTANCE.algorithm)
            assert strategy, "Strategy cannot be defined as None"
            return strategy(executor, test_cluster)
        raise ConfigurationException("Unknown algorithm selected")

    @staticmethod
    def _collect_statistics() -> None:
        tracker = StatisticsTracker()
        for runtime_variable, value in tracker.variables_generator:
            StatisticsTracker().set_output_variable_for_runtime_variable(
                runtime_variable, value
            )

    @staticmethod
    def _track_statistics(
        execution_result: ExecutionResult,
        test_chromosome: tsc.TestSuiteChromosome,
        failing_test_chromosome: tsc.TestSuiteChromosome,
    ) -> None:
        tracker = StatisticsTracker()
        tracker.current_individual(test_chromosome)
        tracker.track_output_variable(RuntimeVariable.Size, test_chromosome.size)
        tracker.track_output_variable(
            RuntimeVariable.Length, test_chromosome.total_length_of_test_cases
        )
        tracker.track_output_variable(
            RuntimeVariable.Coverage, execution_result.branch_coverage / 100
        )
        tracker.track_output_variable(
            RuntimeVariable.FailingSize, failing_test_chromosome.size
        )
        tracker.track_output_variable(
            RuntimeVariable.FailingLength,
            failing_test_chromosome.total_length_of_test_cases,
        )

    @staticmethod
    def _print_results(
        test_cases: List[tc.TestCase],
        failing_test_cases: List[tc.TestCase],
        result: ExecutionResult,
    ) -> None:
        print()
        print()
        print("== Results ============================================================")
        print()
        print(f"Generated {len(test_cases)} test cases")
        print(f"Generated {len(failing_test_cases)} failing test cases")
        print(f"Branch Coverage: {result.branch_coverage:.2f}%")
        timers = Timer.timers
        for timer, value in Timer.timers.items():
            print(f"{timer}: {value:.5f}s")
            if timers.count(timer) > 1:
                print(f"  {timer} count: {timers.count(timer)}")
                print(f"  {timer} min: {timers.min(timer):.5f}s")
                print(f"  {timer} mean: {timers.mean(timer):.5f}s")
                print(f"  {timer} median: {timers.median(timer):.5f}s")
                print(f"  {timer} max: {timers.max(timer):.5f}s")
                print(f"  {timer} stddev: {timers.std_dev(timer):.5f}s")

        print()
        print()
        tracker = StatisticsTracker()
        variables: Dict[RuntimeVariable, Any] = {}
        for variable, value in tracker.variables_generator:
            # Iterating over the variables of the StatisticsTracker clears them from
            # the internal queue, thus we need to store these variables.
            # TODO This should be improved
            variables[variable] = value
            print(f"{variable.value}: {value}")

    @staticmethod
    def _export_test_cases(test_cases: List[tc.TestCase], suffix: str = "") -> None:
        """Export the given test cases.

        :param suffix Suffix that can be added to the file name to distinguish
            between different results e.g., failing and succeeding test cases.
        """
        exporter = ExportProvider.get_exporter()
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
