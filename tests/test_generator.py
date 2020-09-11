#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.generator as gen
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.generation.algorithms.wspy.wholesuiteteststrategy import (
    WholeSuiteTestStrategy,
)
from pynguin.utils.exceptions import ConfigurationException


def test_init_with_configuration():
    conf = MagicMock(log_file=None)
    gen.Pynguin(configuration=conf)
    assert config.INSTANCE == conf


def test_init_without_params():
    with pytest.raises(ConfigurationException) as exception:
        gen.Pynguin(None)
    assert exception.value.args[0] == (
        "Cannot initialise test generator without " + "proper configuration."
    )


def test_instantiate_test_generation_strategy_unknown():
    config.INSTANCE.algorithm = MagicMock()
    with pytest.raises(ConfigurationException):
        gen.Pynguin._instantiate_test_generation_strategy(MagicMock(), MagicMock())


@pytest.mark.parametrize(
    "value,cls",
    [
        (config.Algorithm.RANDOOPY, RandomTestStrategy),
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


def test_run(tmp_path):
    generator = gen.Pynguin(
        configuration=MagicMock(log_file=None, project_path=tmp_path / "nope")
    )
    with mock.patch.object(gen.Pynguin, "_run") as run_mock:
        generator.run()
        run_mock.assert_called_once()
