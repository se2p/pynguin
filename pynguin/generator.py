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
from typing import Union, List

import pynguin.configuration as config
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils.exceptions import ConfigurationException

# pylint: disable=too-few-public-methods
from pynguin.utils.recorder import CoverageRecorder


class Pynguin:
    """The basic interface of the test generator."""

    def __init__(
        self,
        argument_parser: argparse.ArgumentParser = None,
        arguments: List[str] = None,
        configuration: config.Configuration = None,
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
            config.INSTANCE = argument_parser.parse_args(arguments).config
        else:
            raise ConfigurationException(
                "Cannot initialise test generator without proper configuration."
            )
        self._logger = self._setup_logging(
            config.INSTANCE.verbosity, config.INSTANCE.log_file,
        )

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
        executor = TestCaseExecutor()
        coverage_recorder = CoverageRecorder()

        algorithm: TestGenerationStrategy = RandomTestStrategy(
            recorder=coverage_recorder, executor=executor
        )
        test_cases, failing_test_cases = algorithm.generate_sequences()

        self._print_results(len(test_cases), len(failing_test_cases))

        return status

    @staticmethod
    def _print_results(num_test_cases, num_failing_test_cases):
        print(f"Generated {num_test_cases} test cases")
        print(f"Generated {num_failing_test_cases} failing test cases")

    @staticmethod
    def _setup_logging(
        verbosity: config.Verbosity, log_file: Union[str, os.PathLike] = None,
    ) -> logging.Logger:
        logger = logging.getLogger("pynguin")
        logger.setLevel(logging.DEBUG)
        if verbosity is config.Verbosity.VERBOSE:
            level = logging.DEBUG
        elif verbosity is config.Verbosity.QUIET:
            level = logging.NOTSET
        else:
            level = logging.INFO
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

        if verbosity is not config.Verbosity.QUIET:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(
                logging.Formatter("[%(levelname)s](%(name)s): %(message)s")
            )
            logger.addHandler(console_handler)
        else:
            logger.addHandler(logging.NullHandler())

        return logger
