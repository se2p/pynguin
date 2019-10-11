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
"""Provides a configuration interface for the test generator."""
import argparse
import dataclasses
import os
from typing import Union, List, Any


# pylint: disable=too-many-instance-attributes
@dataclasses.dataclass(repr=True, eq=True)
class Configuration:
    """Encapsulates the configuration settings for the test generator."""

    verbose: bool = False
    quiet: bool = False
    log_file: Union[str, os.PathLike] = ""
    seed: int = 42
    project_path: str = ""
    module_names: List[str] = dataclasses.field(default_factory=list)
    measure_coverage: bool = False
    coverage_filename: Union[str, os.PathLike] = ""
    budget: int = 0
    output_folder: Union[str, os.PathLike] = ""
    use_type_hints: bool = False
    record_types: bool = False
    max_sequence_length: int = 0
    max_sequences_combined: int = 0
    counter_threshold: int = 0
    tests_output: Union[str, os.PathLike] = ""
    export_strategy: Any = None


# pylint: disable=too-many-instance-attributes
class ConfigurationBuilder:
    """A builder for configuration a test-generator configuration."""

    def __init__(self) -> None:
        self._verbose: bool = False
        self._quiet: bool = False
        self._log_file: Union[str, os.PathLike] = ""
        self._seed: int = 42
        self._project_path: str = ""
        self._module_names: List[str] = []
        self._measure_coverage: bool = False
        self._coverage_filename: Union[str, os.PathLike] = ""
        self._budget: int = 0
        self._output_folder: Union[str, os.PathLike] = ""
        self._use_type_hints: bool = False
        self._record_types: bool = False
        self._max_sequence_length: int = 0
        self._max_sequences_combined: int = 0
        self._counter_threshold: int = 0
        self._tests_output: Union[str, os.PathLike] = ""
        self._export_strategy = None

    @staticmethod
    def build_from_cli_arguments(
        argument_parser: argparse.ArgumentParser, argv: List[str]
    ) -> Configuration:
        """Build a configuration from CLI arguments.

        :param argument_parser: The argument parser
        :param argv: The list of command-line arguments
        :return: The configuration of the CLI arguments
        """
        config = argument_parser.parse_args(argv)
        return Configuration(  # type: ignore
            verbose=config.verbose,
            quiet=config.quiet,
            log_file=config.log_file,
            seed=config.seed,
            project_path=config.project_path,
            module_names=config.module_names,
            measure_coverage=config.measure_coverage,
            coverage_filename=config.coverage_filename,
            budget=config.budget,
            output_folder=config.output_folder,
            use_type_hints=config.use_type_hints,
            record_types=config.record_types,
            max_sequence_length=config.max_sequence_length,
            max_sequences_combined=config.max_sequences_combined,
            counter_threshold=config.counter_threshold,
            tests_output=config.tests_output,
            export_strategy=config.export_strategy,
        )

    def set_verbose(self) -> "ConfigurationBuilder":
        """Sets the verbose property."""
        self._verbose = True
        return self

    def set_quiet(self) -> "ConfigurationBuilder":
        """Sets the quiet property."""
        self._quiet = True
        return self

    def set_log_file(self, log_file: Union[str, os.PathLike]) -> "ConfigurationBuilder":
        """Sets the log file property."""
        self._log_file = log_file
        return self

    def set_seed(self, seed: int) -> "ConfigurationBuilder":
        """Sets the seed for the random module."""
        self._seed = seed
        return self

    def set_project_path(self, project_path: str) -> "ConfigurationBuilder":
        """Sets the path to the project for which tests should be generated"""
        self._project_path = project_path
        return self

    def set_module_names(self, module_names: List[str]) -> "ConfigurationBuilder":
        """A list of module names for which tests should be generated"""
        self._module_names = module_names
        return self

    def set_measure_coverage(self) -> "ConfigurationBuilder":
        """Sets whether coverage should be measured during test generation"""
        self._measure_coverage = True
        return self

    def set_coverage_filename(
        self, coverage_filename: Union[str, os.PathLike]
    ) -> "ConfigurationBuilder":
        """Sets the file name where the coverage information should be stored."""
        self._coverage_filename = coverage_filename
        return self

    def set_budget(self, budget: int) -> "ConfigurationBuilder":
        """Sets the time budget (in seconds) the generation can take."""
        self._budget = budget
        return self

    def set_output_folder(
        self, output_folder: Union[str, os.PathLike]
    ) -> "ConfigurationBuilder":
        """Sets the output folder."""
        self._output_folder = output_folder
        return self

    def use_type_hints(self) -> "ConfigurationBuilder":
        """Use type hints for test generation."""
        self._use_type_hints = True
        return self

    def record_types(self) -> "ConfigurationBuilder":
        """Record types during test generation."""
        self._record_types = True
        return self

    def set_max_sequence_length(self, length: int) -> "ConfigurationBuilder":
        """Sets the maximum length of generated sequences."""
        self._max_sequence_length = length
        return self

    def set_max_sequences_combined(self, number: int) -> "ConfigurationBuilder":
        """Sets the maximum number of combined sequences."""
        self._max_sequences_combined = number
        return self

    def set_counter_threshold(self, threshold: int) -> "ConfigurationBuilder":
        """Sets the counter threshold."""
        self._counter_threshold = threshold
        return self

    def set_tests_output(
        self, tests_output: Union[str, os.PathLike]
    ) -> "ConfigurationBuilder":
        """Sets the test output folder."""
        self._tests_output = tests_output
        return self

    def set_export_strategy(self, strategy) -> "ConfigurationBuilder":
        """Defines the export strategy to export tests cases."""
        self._export_strategy = strategy
        return self

    def build(self) -> Configuration:
        """Builds the configuration."""
        return Configuration(  # type: ignore
            verbose=self._verbose,
            quiet=self._quiet,
            log_file=self._log_file,
            seed=self._seed,
            project_path=self._project_path,
            module_names=self._module_names,
            measure_coverage=self._measure_coverage,
            coverage_filename=self._coverage_filename,
            budget=self._budget,
            output_folder=self._output_folder,
            use_type_hints=self._use_type_hints,
            record_types=self._record_types,
            max_sequence_length=self._max_sequence_length,
            max_sequences_combined=self._max_sequences_combined,
            counter_threshold=self._counter_threshold,
            tests_output=self._tests_output,
            export_strategy=self._export_strategy,
        )
