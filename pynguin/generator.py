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
import importlib
import logging
import os
import sys
from typing import Union, List, Type

from coverage import Coverage  # type: ignore

from pynguin.configuration import Configuration, ConfigurationBuilder
from pynguin.generation.algorithms.algorithm import GenerationAlgorithm
from pynguin.generation.algorithms.random_algorithm import RandomGenerationAlgorithm
from pynguin.generation.executor import Executor
from pynguin.generation.export.exporter import Exporter
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.recorder import CoverageRecorder
from pynguin.utils.statements import Sequence
from pynguin.utils.string import String


# pylint: disable=too-few-public-methods
class Pynguin:
    """The basic interface of the test generator."""

    def __init__(
        self,
        argument_parser: argparse.ArgumentParser = None,
        arguments: List[str] = None,
        configuration: Configuration = None,
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
            self._configuration = configuration
        elif argument_parser and arguments:
            self._configuration = ConfigurationBuilder.build_from_cli_arguments(
                argument_parser, arguments
            )
        else:
            raise ConfigurationException(
                "Cannot initialise test generator without proper configuration."
            )
        self._logger = self._setup_logging(
            self._configuration.verbose,
            self._configuration.quiet,
            self._configuration.log_file,
        )

    def run(self) -> int:
        """Run"""
        if not self._logger:
            raise ConfigurationException()

        try:
            self._logger.info("Start Pynguin Test Generation…")
            return self._run_execution()
        finally:
            self._logger.info("Stop Pynguin Test Generation…")

    def _run_execution(self) -> int:
        exit_status = 0

        sys.path.insert(0, self._configuration.project_path)
        executor = Executor(
            self._configuration.module_names,
            measure_coverage=self._configuration.measure_coverage,
        )

        objects_under_test: List[Type] = []
        coverage_filename = f"{self._configuration.seed}.csv"
        coverage_recorder = CoverageRecorder(
            modules=[],
            store=True,
            file_name=coverage_filename,
            folder=os.path.join(self._configuration.output_folder, "coverage_total"),
        )
        for module in self._configuration.module_names:
            imported_module = importlib.import_module(module)
            objects_under_test.append(imported_module)  # type: ignore
            coverage_recorder.add_module(imported_module)  # type: ignore

        algorithm: GenerationAlgorithm = RandomGenerationAlgorithm(
            recorder=coverage_recorder,
            executor=executor,
            configuration=self._configuration,
        )
        sequences, error_sequences = algorithm.generate_sequences(
            self._configuration.budget, objects_under_test
        )

        if self._configuration.measure_coverage:
            self._store_all_coverage_data(
                coverage_recorder,
                executor,
                coverage_filename,
                sequences,
                error_sequences,
                self._configuration.seed,
            )

        self._store_symbol_table(algorithm)
        self._print_results(sequences, error_sequences, executor.accumulated_coverage)

        strings_filename = os.path.join(
            self._configuration.output_folder,
            "string",
            f"{self._configuration.seed}.txt",
        )
        os.makedirs(os.path.dirname(strings_filename), exist_ok=True)
        with open(strings_filename, mode="w") as out_file:
            for string in String.observed:
                out_file.write(f"{string}\n")

        if self._configuration.tests_output:
            exporter = Exporter(self._configuration)
            exporter.export_sequences(sequences)

        return exit_status

    # pylint: disable=too-many-arguments
    def _store_all_coverage_data(
        self,
        coverage_recorder: CoverageRecorder,
        executor: Executor,
        coverage_filename: str,
        sequences: List[Sequence],
        error_sequences: List[Sequence],
        seed: int,
    ) -> None:
        coverage_recorder.save()
        self._store_coverage(
            executor.load_coverage,
            os.path.join(self._configuration.output_folder, "coverage_base"),
            coverage_filename,
        )

        executor.load_coverage.html_report(
            directory=os.path.join(
                self._configuration.coverage_filename, str(seed), "base",
            ),
        )
        executor.accumulated_coverage.html_report(
            directory=os.path.join(self._configuration.coverage_filename, str(seed))
        )

        coverage = self._re_execute_sequences(sequences)
        self._store_coverage(
            coverage,
            os.path.join(self._configuration.output_folder, "coverage"),
            coverage_filename,
        )

        error_coverage = self._re_execute_sequences(error_sequences)
        self._store_coverage(
            error_coverage,
            os.path.join(self._configuration.output_folder, "coverage_error"),
            coverage_filename,
        )

    def _re_execute_sequences(self, sequences: List[Sequence],) -> Coverage:
        executor = Executor(self._configuration.module_names, measure_coverage=True)
        executor.load_modules(reload=True)
        for sequence in sequences:
            executor.execute(sequence)
        return executor.accumulated_coverage

    @staticmethod
    def _store_coverage(
        coverage: Coverage, path: Union[str, os.PathLike], file_name: str,
    ):
        recorder = CoverageRecorder(
            store=True, file_name=file_name, folder=path, modules=[]
        )
        recorder.record_data(coverage)
        recorder.save()

    def _store_symbol_table(self, algorithm: GenerationAlgorithm) -> None:
        pass

    def _print_results(
        self,
        sequences: List[Sequence],
        error_sequences: List[Sequence],
        coverage: Coverage,
    ) -> None:
        result_string = (
            "Results:\n"
            "Sequence   \t \t Number\n"
            "----------------------------------------------------------\n"
            "Seqs       \t \t " + str(len(sequences)) + "\n"
            "Error seqs \t \t " + str(len(error_sequences)) + "\n"
            "----------------------------------------------------------\n"
            "\n"
            "Observed Strings:\n"
            + str(String.observed)
            + "----------------------------------------------------------\n"
            "Coverage: " + str(coverage.get_data())
        )
        self._logger.info(result_string)

    @staticmethod
    def _setup_logging(
        verbose: bool = False,
        quiet: bool = False,
        log_file: Union[str, os.PathLike] = None,
    ) -> logging.Logger:
        logger = logging.getLogger("pynguin")
        logger.setLevel(logging.DEBUG)
        if verbose:
            level = logging.DEBUG
        elif quiet:
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

        if not quiet:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(
                logging.Formatter("[%(levelname)s](%(name)s): %(message)s")
            )
            logger.addHandler(console_handler)
        else:
            logger.addHandler(logging.NullHandler())

        return logger
