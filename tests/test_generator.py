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
import importlib
import logging
import os
import shutil
import tempfile
from argparse import ArgumentParser
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.generator import Pynguin
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.string import String


@pytest.fixture
def configuration():
    return config.Configuration(
        algorithm=config.Algorithm.RANDOOPY,
        verbosity=config.Verbosity.QUIET,
        log_file="",
        module_names=[],
        output_path="",
        project_path="",
    )


def test__setup_logging_standard_with_log_file():
    log_fd, log_file = tempfile.mkstemp()
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(
        log_file=log_file, verbosity=config.Verbosity.NORMAL
    )
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 2
    logging.shutdown()
    os.close(log_fd)
    os.remove(log_file)
    importlib.reload(logging)


def test__setup_logging_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(config.Verbosity.VERBOSE)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_quiet_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(config.Verbosity.QUIET)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
    logging.shutdown()
    importlib.reload(logging)


def test_init_with_configuration(configuration):
    Pynguin(configuration=configuration)
    assert config.INSTANCE == configuration


def test_init_without_params():
    with pytest.raises(ConfigurationException) as exception:
        Pynguin()
    assert (
        exception.value.args[0] == "Cannot initialise test generator without "
        "proper configuration."
    )


def test_init_with_cli_arguments(configuration):
    option_mock = MagicMock(config=configuration)
    parser = MagicMock(ArgumentParser)
    parser.parse_args.return_value = option_mock
    args = [""]
    Pynguin(argument_parser=parser, arguments=args)
    assert config.INSTANCE == configuration


@pytest.mark.skip()
@mock.patch("pynguin.generator.Executor")
@mock.patch("pynguin.generator.CoverageRecorder")
@mock.patch("pynguin.generator.RandomGenerationAlgorithm")
def test_run(algorithm, __, ___):
    algorithm.return_value.generate_sequences.return_value = ([], [])

    tmp_dir = tempfile.mkdtemp()
    configuration = config.Configuration(output_path=tmp_dir)
    generator = Pynguin(configuration=configuration)
    assert generator.run() == 0
    shutil.rmtree(tmp_dir)


@pytest.mark.skip()
@mock.patch("pynguin.generator.Executor")
@mock.patch("pynguin.generator.CoverageRecorder")
@mock.patch("pynguin.generator.RandomGenerationAlgorithm")
def test_run_with_module_names_and_coverage(algorithm, _, __):
    algorithm.return_value.generate_sequences.return_value = ([], [])

    tmp_dir = tempfile.mkdtemp()
    configuration = config.Configuration(
        output_path=tmp_dir, module_names=["foo"], measure_coverage=True
    )
    generator = Pynguin(configuration=configuration)
    with mock.patch("pynguin.generator.importlib.import_module") as import_mock:
        import_mock.return_value = "bar"
        generator.run()

    shutil.rmtree(tmp_dir)


@pytest.mark.skip()
@mock.patch("pynguin.generator.Executor")
@mock.patch("pynguin.generator.CoverageRecorder")
@mock.patch("pynguin.generator.RandomGenerationAlgorithm")
def test_run_with_observed_string(algorithm, _, __):
    algorithm.return_value.generate_sequences.return_value = ([], [])
    String.observed.append("foo")
    String.observed.append("bar")

    tmp_dir = tempfile.mkdtemp()
    configuration = config.Configuration(output_path=tmp_dir)
    generator = Pynguin(configuration=configuration)
    generator.run()

    with open(os.path.join(tmp_dir, "string", "42.txt")) as f:
        lines = f.readlines()
        assert "foo\n" in lines
        assert "bar\n" in lines

    shutil.rmtree(tmp_dir)


def test_run_without_logger(configuration):
    generator = Pynguin(configuration=configuration)
    generator._logger = None
    with pytest.raises(ConfigurationException):
        generator.run()
