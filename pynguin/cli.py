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
import sys
from pathlib import Path
from typing import List, Optional

import simple_parsing
from rich.logging import RichHandler
from rich.traceback import install

import pynguin.configuration as config
from pynguin import __version__
from pynguin.generator import run_pynguin, set_configuration
from pynguin.utils.console import console


def _create_argument_parser() -> argparse.ArgumentParser:
    parser = simple_parsing.ArgumentParser(
        add_option_string_dash_variants=True,
        description="Pynguin is an automatic unit test generation framework for Python",
        fromfile_prefix_chars="@",
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
        "--log-file",
        "--log_file",
        dest="log_file",
        type=str,
        default=None,
        help="Path to store the log file.",
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


def _setup_output_path(output_path: str) -> None:
    path = Path(output_path).resolve()
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def _setup_logging(
    verbosity: int,
    log_file: Optional[str] = None,
):
    default_log_format = (
        "%(asctime)s [%(levelname)s](%(name)s:%(funcName)s:%(lineno)d): %(message)s"
    )
    logger = logging.getLogger("")  # get root logger
    logger.setLevel(logging.DEBUG)
    default_formatter = logging.Formatter(fmt=default_log_format, datefmt="%X")
    if log_file:
        log_file_path = Path(log_file).resolve()
        if not log_file_path.parent.exists():
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(default_formatter)
        logger.addHandler(file_handler)

    if verbosity < 0:
        logger.addHandler(logging.NullHandler())
    else:
        level = logging.WARNING
        if verbosity == 1:
            level = logging.INFO
        if verbosity >= 2:
            level = logging.DEBUG

        console_handler = RichHandler(
            rich_tracebacks=True, log_time_format="[%X]", console=console
        )
        console_handler.setLevel(level)
        console_handler.setFormatter(logging.Formatter("%(message)s"))
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
    install()
    if argv is None:
        argv = sys.argv
    if len(argv) <= 1:
        argv.append("--help")
    argv = _expand_arguments_if_necessary(argv[1:])

    argument_parser = _create_argument_parser()
    parsed = argument_parser.parse_args(argv)
    _setup_output_path(parsed.config.output_path)
    _setup_logging(parsed.verbosity, parsed.log_file)

    set_configuration(parsed.config)
    with console.status("Running Pynguin..."):
        return run_pynguin().value


if __name__ == "__main__":
    sys.exit(main(sys.argv))
