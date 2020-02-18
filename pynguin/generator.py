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
"""Entry"""
import argparse
import logging
import os
import sys
from typing import Union, List, Optional

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.export.exportprovider import ExportProvider
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException


# pylint: disable=too-few-public-methods
class Pynguin:
    """The basic interface of the test generator."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        argument_parser: argparse.ArgumentParser = None,
        arguments: List[str] = None,
        configuration: config.Configuration = None,
        verbosity: int = -1,
        log_file: Optional[str] = None,
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
            log_file = parsed.log_file
        else:
            raise ConfigurationException(
                "Cannot initialise test generator without proper configuration."
            )
        self._logger = self._setup_logging(verbosity, log_file)

    def run(self) -> int:
        """Run"""
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
        # TODO(fk) the current simple_parse does not support Optional values:
        # https://github.com/lebrice/SimpleParsing/issues/14
        if config.INSTANCE.seed != 0:
            randomness.RNG.seed(config.INSTANCE.seed)

        with install_import_hook(
            config.INSTANCE.algorithm.use_instrumentation, config.INSTANCE.module_name
        ):
            executor = TestCaseExecutor()

            algorithm: TestGenerationStrategy = RandomTestStrategy(executor)
            test_cases, failing_test_cases = algorithm.generate_sequences()

            executor = TestCaseExecutor()
            result = executor.execute_test_suite(test_cases)

            self._print_results(len(test_cases), len(failing_test_cases))
            self._logger.info("Export successful test cases")
            self._export_test_cases(test_cases)
            self._logger.info("Export failing test cases")
            self._export_test_cases(failing_test_cases, "_failing")
            print(f"Branch Coverage: {result.branch_coverage:.2f}%")

        return status

    @staticmethod
    def _print_results(num_test_cases, num_failing_test_cases):
        print(f"Generated {num_test_cases} test cases")
        print(f"Generated {num_failing_test_cases} failing test cases")

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
