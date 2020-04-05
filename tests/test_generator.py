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
from argparse import ArgumentParser
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.generation.algorithms.randoopy.randomtestmonkeytypestrategy import (
    RandomTestMonkeyTypeStrategy,
)
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.wspy.wholesuiteteststrategy import (
    WholeSuiteTestStrategy,
)
from pynguin.generator import Pynguin
from pynguin.utils.exceptions import ConfigurationException


def test__setup_logging_standard_with_log_file(tmp_path):
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(
        log_file=str(tmp_path / "pynguin-test.log"), verbosity=0
    )
    assert isinstance(logger, logging.Logger)
    assert logger.level == logging.DEBUG
    assert len(logger.handlers) == 2
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_single_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(1)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.INFO
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_double_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(2)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_quiet_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = Pynguin._setup_logging(-1)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
    logging.shutdown()
    importlib.reload(logging)


def test_init_with_configuration():
    conf = MagicMock(log_file=None)
    Pynguin(configuration=conf)
    assert config.INSTANCE == conf


def test_init_without_params():
    with pytest.raises(ConfigurationException) as exception:
        Pynguin()
    assert (
        exception.value.args[0] == "Cannot initialise test generator without "
        "proper configuration."
    )


def test_init_with_cli_arguments():
    conf = MagicMock(log_file=None)
    option_mock = MagicMock(config=conf, verbosity=0)
    parser = MagicMock(ArgumentParser)
    parser.parse_args.return_value = option_mock
    args = [""]
    Pynguin(argument_parser=parser, arguments=args)
    assert config.INSTANCE == conf


def test_run_without_logger():
    generator = Pynguin(configuration=MagicMock(log_file=None))
    generator._logger = None
    with pytest.raises(ConfigurationException):
        generator.run()


def test_instantiate_test_generation_strategy_unknown():
    config.INSTANCE.algorithm = MagicMock()
    with pytest.raises(ConfigurationException):
        Pynguin._instantiate_test_generation_strategy(MagicMock(), MagicMock())


@pytest.mark.parametrize(
    "value,cls",
    [
        (config.Algorithm.RANDOOPY, RandomTestStrategy),
        (config.Algorithm.RANDOOPY_MONKEYTYPE, RandomTestMonkeyTypeStrategy),
        (config.Algorithm.WSPY, WholeSuiteTestStrategy),
    ],
)
def test_instantiate_test_generation_strategy_actual(value, cls):
    config.INSTANCE.algorithm = value
    instance = Pynguin._instantiate_test_generation_strategy(MagicMock(), MagicMock())
    assert isinstance(instance, cls)
