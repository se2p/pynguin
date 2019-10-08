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
import tempfile
from argparse import ArgumentParser
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pynguin.configuration import Configuration
from pynguin.generator import Pynguin
from pynguin.utils.exceptions import ConfigurationException


@pytest.fixture
def configuration():
    return Configuration(verbose=False, quiet=True, log_file="")


def test__setup_logging_standard_with_log_file():
    _, log_file = tempfile.mkstemp()
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(log_file=log_file)
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 2
    os.remove(log_file)
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(verbose=True)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_quiet_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(quiet=True)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
    logging.shutdown()
    importlib.reload(logging)


def test_init_with_configuration(configuration):
    generator = Pynguin(configuration=configuration)
    assert generator._configuration == configuration


def test_init_without_params():
    with pytest.raises(ConfigurationException) as exception:
        Pynguin()
    assert (
        exception.value.args[0] == "Cannot initialise test generator without "
        "proper configuration."
    )


def test_init_with_cli_arguments(configuration):
    parser = MagicMock(ArgumentParser)
    args = [""]
    with mock.patch(
        "pynguin.generator.ConfigurationBuilder.build_from_cli_arguments"
    ) as builder_mock:
        builder_mock.return_value = configuration
        generator = Pynguin(argument_parser=parser, arguments=args)
        assert generator._configuration == configuration


def test_run(configuration):
    generator = Pynguin(configuration=configuration)
    assert generator.run() == 1


def test_run_without_logger(configuration):
    generator = Pynguin(configuration=configuration)
    generator._logger = None
    with pytest.raises(ConfigurationException):
        generator.run()
