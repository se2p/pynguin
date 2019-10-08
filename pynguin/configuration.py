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
from typing import Union, List


# pylint: disable=too-many-instance-attributes
@dataclasses.dataclass(repr=True, eq=True)
class Configuration:
    """Encapsulates the configuration settings for the test generator."""

    verbose: bool = False
    quiet: bool = False
    log_file: Union[str, os.PathLike] = ""
    seed: int = 42
    project_path: Union[str, os.PathLike] = ""
    module_names: List[str] = dataclasses.field(default_factory=list)
    measure_coverage: bool = False
    coverage_filename: Union[str, os.PathLike] = ""
    budget: int = 0


# pylint: disable=too-many-instance-attributes
class ConfigurationBuilder:
    """A builder for configuration a test-generator configuration."""

    def __init__(self) -> None:
        self._verbose: bool = False
        self._quiet: bool = False
        self._log_file: Union[str, os.PathLike] = ""
        self._seed: int = 42
        self._project_path: Union[str, os.PathLike] = ""
        self._module_names: List[str] = []
        self._measure_coverage: bool = False
        self._coverage_filename: Union[str, os.PathLike] = ""
        self._budget: int = 0

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
        return Configuration(
            verbose=config.verbose,
            quiet=config.quiet,
            log_file=config.log_file,
            seed=config.seed,
            project_path=config.project_path,
            module_names=config.module_names,
            measure_coverage=config.measure_coverage,
            coverage_filename=config.coverage_filename,
            budget=config.budget,
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

    def set_project_path(
        self, project_path: Union[str, os.PathLike]
    ) -> "ConfigurationBuilder":
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

    def build(self) -> Configuration:
        """Builds the configuration."""
        return Configuration(
            verbose=self._verbose,
            quiet=self._quiet,
            log_file=self._log_file,
            seed=self._seed,
            project_path=self._project_path,
            module_names=self._module_names,
            measure_coverage=self._measure_coverage,
            coverage_filename=self._coverage_filename,
            budget=self._budget,
        )
