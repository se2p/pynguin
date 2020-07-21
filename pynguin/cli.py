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

This module provides the main entry location for the program execution from the command
line.
"""
import argparse
import logging
import os
import sys
from typing import List, Union

import simple_parsing

from pynguin import Configuration, __version__
from pynguin.generator import Pynguin


def _create_argument_parser() -> argparse.ArgumentParser:
    parser = simple_parsing.ArgumentParser(
        description="Pynguin is an automatic random unit test generation framework for Python."
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbosity",
        default=0,
        help="verbose output (repeat for increased verbosity)",
    )
    parser.add_argument(
        "--log_file", type=str, default=None, help="Path to store the log file."
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_const",
        const=-1,
        default=0,
        dest="verbosity",
        help="quiet output",
    )
    parser.add_arguments(Configuration, dest="config")

    return parser


def _expand_arguments_if_necessary(arguments: List[str]) -> List[str]:
    """Hacky way to pass comma separated output variables.
    Should be eliminated asap."""
    if "--output_variables" not in arguments:
        return arguments
    index = arguments.index("--output_variables")
    if "," not in arguments[index + 1]:
        return arguments
    variables = arguments[index + 1].split(",")
    output = arguments[: index + 1] + variables + arguments[index + 2 :]
    return output


def _setup_logging(
    verbosity: int, log_file: Union[str, os.PathLike] = None,
):
    # TODO(fk) use logging.basicConfig

    # Configure root logger
    logger = logging.getLogger("")
    logger.setLevel(logging.DEBUG)

    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s](%(name)s:%(funcName)s:%(lineno)d): "
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


def main(argv: List[str] = None) -> int:
    """Entry point of the Pynguin automatic unit test generation framework.

    Args:
        argv: List of command-line arguments

    Returns:
        An integer representing the success of the program run.  0 means
        success, all non-zero exit codes indicate errors.
    """
    if argv is None:
        argv = sys.argv
    if len(argv) <= 1:
        argv.append("--help")
    argv = _expand_arguments_if_necessary(argv[1:])

    argument_parser = _create_argument_parser()
    parsed = argument_parser.parse_args(argv)
    _setup_logging(parsed.verbosity, parsed.log_file)

    generator = Pynguin(parsed.config)
    return generator.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
