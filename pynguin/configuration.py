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


@dataclasses.dataclass(repr=True, eq=True)
class Configuration:
    """Encapsulates the configuration settings for the test generator."""

    verbose: bool
    quiet: bool
    log_file: Union[str, os.PathLike]


class ConfigurationBuilder:
    """A builder for configuration a test-generator configuration."""

    def __init__(self) -> None:
        self._verbose: bool = False
        self._quiet: bool = False
        self._log_file: Union[str, os.PathLike] = ""

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
            verbose=config.verbose, quiet=config.quiet, log_file=config.log_file
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

    def build(self) -> Configuration:
        """Builds the configuration."""
        return Configuration(
            verbose=self._verbose, quiet=self._quiet, log_file=self._log_file
        )
