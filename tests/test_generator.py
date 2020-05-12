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
from unittest import mock
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
import pynguin.generator as gen
from pynguin.utils.exceptions import ConfigurationException


def test__setup_logging_standard_with_log_file(tmp_path):
    logging.shutdown()
    importlib.reload(logging)
    logger = gen.Pynguin._setup_logging(
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
    logger = gen.Pynguin._setup_logging(1)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.INFO
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_double_verbose_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = gen.Pynguin._setup_logging(2)
    assert len(logger.handlers) == 1
    assert logger.handlers[0].level == logging.DEBUG
    logging.shutdown()
    importlib.reload(logging)


def test__setup_logging_quiet_without_log_file():
    logging.shutdown()
    importlib.reload(logging)
    logger = gen.Pynguin._setup_logging(-1)
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
    logging.shutdown()
    importlib.reload(logging)


def test_init_with_configuration():
    conf = MagicMock(log_file=None)
    gen.Pynguin(configuration=conf)
    assert config.INSTANCE == conf


def test_init_without_params():
    with pytest.raises(ConfigurationException) as exception:
        gen.Pynguin()
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
    gen.Pynguin(argument_parser=parser, arguments=args)
    assert config.INSTANCE == conf


def test_run_without_logger():
    generator = gen.Pynguin(configuration=MagicMock(log_file=None))
    generator._logger = None
    with pytest.raises(ConfigurationException):
        generator.run()


def test_instantiate_test_generation_strategy_unknown():
    config.INSTANCE.algorithm = MagicMock()
    with pytest.raises(ConfigurationException):
        gen.Pynguin._instantiate_test_generation_strategy(MagicMock(), MagicMock())


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
    instance = gen.Pynguin._instantiate_test_generation_strategy(
        MagicMock(), MagicMock()
    )
    assert isinstance(instance, cls)


def test_setup_executor_failed():
    generator = gen.Pynguin(configuration=MagicMock(log_file=None))
    with mock.patch(
        "pynguin.testcase.execution.testcaseexecutor.TestCaseExecutor.__init__"
    ) as exec_mock:
        exec_mock.side_effect = ModuleNotFoundError()
        assert generator._setup_executor(MagicMock()) is None


def test_setup_executor_success():
    generator = gen.Pynguin(configuration=MagicMock(log_file=None))
    with mock.patch(
        "pynguin.testcase.execution.testcaseexecutor.TestCaseExecutor.__init__"
    ) as exec_mock:
        exec_mock.return_value = None
        assert generator._setup_executor(MagicMock())


def test_setup_test_cluster_empty():
    generator = gen.Pynguin(
        configuration=MagicMock(
            log_file=None,
            type_inference_strategy=config.TypeInferenceStrategy.TYPE_HINTS,
        )
    )
    with mock.patch(
        "pynguin.setup.testclustergenerator.TestClusterGenerator.generate_cluster"
    ) as gen_mock:
        tc = MagicMock()
        tc.num_accessible_objects_under_test.return_value = 0
        gen_mock.return_value = tc
        assert generator._setup_test_cluster() is None


def test_setup_test_cluster_not_empty():
    generator = gen.Pynguin(
        configuration=MagicMock(
            log_file=None,
            type_inference_strategy=config.TypeInferenceStrategy.TYPE_HINTS,
        )
    )
    with mock.patch(
        "pynguin.setup.testclustergenerator.TestClusterGenerator.generate_cluster"
    ) as gen_mock:
        tc = MagicMock()
        tc.num_accessible_objects_under_test.return_value = 1
        gen_mock.return_value = tc
        assert generator._setup_test_cluster()


def test_setup_path_and_hook_invalid_dir(tmp_path):
    generator = gen.Pynguin(
        configuration=MagicMock(log_file=None, project_path=tmp_path / "nope")
    )
    assert generator._setup_path_and_hook() is None


def test_setup_path_and_hook_valid_dir(tmp_path):
    module_name = "test_module"
    generator = gen.Pynguin(
        configuration=MagicMock(
            log_file=None, project_path=tmp_path, module_name=module_name
        )
    )
    with mock.patch.object(gen, "install_import_hook") as hook_mock:
        with mock.patch("sys.path") as path_mock:
            assert generator._setup_path_and_hook()
            hook_mock.assert_called_once()
            path_mock.insert.assert_called_with(0, tmp_path)
