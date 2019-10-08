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

from typing import Union, List

from pynguin.configuration import Configuration, ConfigurationBuilder
from pynguin.utils.exceptions import ConfigurationException


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

    def setup(self) -> None:
        """Setup"""

    @staticmethod
    def run() -> int:
        """Run"""
        return 1

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
