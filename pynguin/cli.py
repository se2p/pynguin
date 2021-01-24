#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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

import pynguin.configuration as config
from pynguin import __version__
from pynguin.generator import Pynguin


def _create_argument_parser() -> argparse.ArgumentParser:
    parser = simple_parsing.ArgumentParser(
        add_dest_to_option_strings=False,
        description="Pynguin is an automatic unit test generation framework for Python",
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
    parser.add_arguments(config.Configuration, dest="config")

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
    verbosity: int,
    log_file: Union[str, os.PathLike] = None,
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
                + "%(message)s"
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
    """Entry point for the CLI of the Pynguin automatic unit test generation framework.

    This method behaves like a standard UNIX command-line application, i.e.,
    the return value `0` signals a successful execution.  Any other return value
    signals some errors.  This is, e.g., the case if the framework was not able
    to generate one successfully running test case for the class under test.

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
    return generator.run().value


if __name__ == "__main__":
    sys.exit(main(sys.argv))
