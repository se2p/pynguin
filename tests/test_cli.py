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
import argparse
import importlib
import logging
import os
import tempfile

from pynguin.cli import main, _setup_logging, _create_argument_parser


def test_main_empty_argv():
    assert main() == 0


def test_main_with_argv():
    assert main(["--help"]) == 0


def test__setup_logging_standard_with_log_file():
    _, log_file = tempfile.mkstemp()
    logging.shutdown()
    importlib.reload(logging)
    logger = _setup_logging(log_file=log_file)
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 2
    os.remove(log_file)
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = _setup_logging(verbose=True)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_quiet_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = _setup_logging(quiet=True)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
    logging.shutdown()
    importlib.reload(logging)


def test__create_argument_parser():
    parser = _create_argument_parser()
    assert isinstance(parser, argparse.ArgumentParser)
