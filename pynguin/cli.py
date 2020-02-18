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
import sys
from typing import List

import simple_parsing  # type: ignore

from pynguin import __version__, Configuration
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


def main(argv: List[str] = None) -> int:
    """Entry point of the Pynguin automatic unit test generation framework.

    :arg: argv List of command-line arguments
    :return: An integer representing the success of the program run.  0 means
    success, all non-zero exit codes indicate errors.
    """
    if argv is None:
        argv = sys.argv
    if len(argv) <= 1:
        argv.append("--help")
    parser = _create_argument_parser()
    generator = Pynguin(parser, argv[1:])
    return generator.run()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
