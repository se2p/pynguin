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
from unittest import mock
from unittest.mock import MagicMock, call

import pytest

from pynguin.cli import (
    _create_argument_parser,
    _expand_arguments_if_necessary,
    _setup_logging,
    main,
)
from pynguin.generator import ReturnCode


def test_main_empty_argv():
    with mock.patch("pynguin.cli.Pynguin") as generator_mock:
        with mock.patch("pynguin.cli._create_argument_parser") as parser_mock:
            with mock.patch("pynguin.cli._setup_logging"):
                generator_mock.return_value.run.return_value = ReturnCode.OK
                parser = MagicMock()
                parser_mock.return_value = parser
                main()
                assert len(parser.parse_args.call_args[0][0]) > 0


def test_main_with_argv():
    with mock.patch("pynguin.cli.Pynguin") as generator_mock:
        with mock.patch("pynguin.cli._create_argument_parser") as parser_mock:
            with mock.patch("pynguin.cli._setup_logging"):
                generator_mock.return_value.run.return_value = ReturnCode.OK
                parser = MagicMock()
                parser_mock.return_value = parser
                args = ["foo", "--help"]
                main(args)
                assert parser.parse_args.call_args == call(args[1:])


def test__create_argument_parser():
    parser = _create_argument_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test__setup_logging_standard_with_log_file(tmp_path):
    logging.shutdown()
    importlib.reload(logging)
    _setup_logging(log_file=str(tmp_path / "pynguin-test.log"), verbosity=0)
    logger = logging.getLogger("")
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 2
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_single_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    _setup_logging(1)
    logger = logging.getLogger("")
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.INFO
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_double_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    _setup_logging(2)
    logger = logging.getLogger("")
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_quiet_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    _setup_logging(-1)
    logger = logging.getLogger("")
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
    logging.shutdown()
    importlib.reload(logging)


@pytest.mark.parametrize(
    "arguments, expected",
    [
        pytest.param(
            ["--foo", "bar", "--bar", "foo"], ["--foo", "bar", "--bar", "foo"]
        ),
        pytest.param(
            ["--foo", "bar", "--output_variables", "foo,bar,baz", "--bar", "foo"],
            ["--foo", "bar", "--output_variables", "foo", "bar", "baz", "--bar", "foo"],
        ),
        pytest.param(
            ["--foo", "bar", "--output_variables", "baz", "--bar", "foo"],
            ["--foo", "bar", "--output_variables", "baz", "--bar", "foo"],
        ),
    ],
)
def test__expand_arguments_if_necessary(arguments, expected):
    result = _expand_arguments_if_necessary(arguments)
    assert result == expected
