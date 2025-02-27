#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Pynguin is an automated unit test generation framework for Python.

This module provides the main entry location for the program execution from the command
line.
"""

from __future__ import annotations

import logging
import os
import sys

from pathlib import Path
from typing import TYPE_CHECKING

import simple_parsing

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

import pynguin.configuration as config

from pynguin.__version__ import __version__
from pynguin.generator import run_pynguin
from pynguin.generator import set_configuration
from pynguin.utils.configuration_writer import write_configuration


if TYPE_CHECKING:
    import argparse


def _create_argument_parser() -> argparse.ArgumentParser:
    parser = simple_parsing.ArgumentParser(
        add_option_string_dash_variants=simple_parsing.DashVariant.UNDERSCORE_AND_DASH,
        description="Pynguin is an automatic unit test generation framework for Python",
        fromfile_prefix_chars="@",
    )
    parser.add_argument("--version", action="version", version="%(prog)s " + __version__)
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        dest="verbosity",
        default=0,
        help="verbose output (repeat for increased verbosity)",
    )
    parser.add_argument(
        "--no-rich",
        "--no_rich",
        "--poor",  # hehe
        dest="no_rich",
        action="store_true",
        default=False,
        help="Don't use rich for nicer consoler output.",
    )
    parser.add_argument(
        "--log-file",
        "--log_file",
        help="Path to an optional log file.",
        type=Path,
    )
    parser.add_arguments(config.Configuration, dest="config")

    return parser


def _expand_arguments_if_necessary(arguments: list[str]) -> list[str]:
    """Expand command-line arguments, if necessary.

    This is a hacky way to pass comma separated output variables.  The reason to have
    this is an issue with the automatically-generated bash scripts for Pynguin cluster
    execution, for which I am not able to solve the (I assume) globbing issues.  This
    function allows to provide the output variables either separated by spaces or by
    commas, which works as a work-around for the aforementioned problem.

    This function replaces the commas for the ``--output-variables`` parameter and
    the ``--coverage-metrics`` by spaces that can then be handled by the argument-
    parsing code.

    Args:
        arguments: The list of command-line arguments
    Returns:
        The (potentially) processed list of command-line arguments
    """
    if (
        "--output_variables" not in arguments
        and "--output-variables" not in arguments
        and "--coverage_metrics" not in arguments
        and "--coverage-metrics" not in arguments
    ):
        return arguments
    if "--output_variables" in arguments:
        arguments = _parse_comma_separated_option(arguments, "--output_variables")
    elif "--output-variables" in arguments:
        arguments = _parse_comma_separated_option(arguments, "--output-variables")

    if "--coverage_metrics" in arguments:
        arguments = _parse_comma_separated_option(arguments, "--coverage_metrics")
    elif "--coverage-metrics" in arguments:
        arguments = _parse_comma_separated_option(arguments, "--coverage-metrics")
    return arguments


def _parse_comma_separated_option(arguments: list[str], option: str) -> list[str]:
    index = arguments.index(option)
    if "," not in arguments[index + 1]:
        return arguments
    variables = arguments[index + 1].split(",")
    return arguments[: index + 1] + variables + arguments[index + 2 :]


def _setup_output_path(output_path: str) -> None:
    path = Path(output_path).resolve()
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def _setup_logging(
    verbosity: int,
    no_rich: bool,  # noqa: FBT001
    log_file: Path | None,
) -> Console | None:
    level = logging.WARNING
    if log_file is not None:
        level = logging.INFO
    if verbosity == 1:
        level = logging.INFO
    if verbosity >= 2:
        level = logging.DEBUG

    console = None
    handler: logging.Handler
    if no_rich:
        handler = logging.StreamHandler()
    else:
        install()
        console = Console(tab_size=4)
        handler = RichHandler(rich_tracebacks=True, log_time_format="[%X]", console=console)
        handler.setFormatter(logging.Formatter("%(message)s"))

    if log_file is not None:
        handler = logging.FileHandler(log_file)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s](%(name)s:%(funcName)s:%(lineno)d): %(message)s",
        datefmt="[%X]",
        handlers=[handler],
    )
    return console


# People may wipe their disk, so we give them a heads-up.
_DANGER_ENV = "PYNGUIN_DANGER_AWARE"


def main(argv: list[str] | None = None) -> int:
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
    if _DANGER_ENV not in os.environ:
        print(  # noqa: T201
            f"""Environment variable '{_DANGER_ENV}' not set.
Aborting to avoid harming your system.
Please refer to the documentation
(https://pynguin.readthedocs.io/en/latest/user/quickstart.html)
to see why this happens and what you must do to prevent it."""
        )
        return -1

    if argv is None:
        argv = sys.argv
    if len(argv) <= 1:
        argv.append("--help")
    argv = _expand_arguments_if_necessary(argv[1:])

    argument_parser = _create_argument_parser()
    parsed = argument_parser.parse_args(argv)

    _setup_output_path(parsed.config.test_case_output.output_path)

    console = _setup_logging(
        verbosity=parsed.verbosity,
        no_rich=parsed.no_rich,
        log_file=parsed.log_file,
    )

    set_configuration(parsed.config)
    write_configuration()
    if console is not None:
        with console.status("Running Pynguin..."):
            return run_pynguin().value
    else:
        return run_pynguin().value


if __name__ == "__main__":
    import multiprocess as mp

    mp.set_start_method("spawn")

    sys.exit(main(sys.argv))
