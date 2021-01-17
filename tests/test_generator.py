#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.generator as gen


def test_init_with_configuration():
    conf = MagicMock(log_file=None)
    gen.Pynguin(configuration=conf)
    assert config.INSTANCE == conf


def test__load_sut_failed():
    generator = gen.Pynguin(
        configuration=MagicMock(log_file=None, module_name="this.does.not.exist")
    )
    assert generator._load_sut() is False


def test__load_sut_success():
    generator = gen.Pynguin(configuration=MagicMock(log_file=None))
    with mock.patch("importlib.import_module"):
        assert generator._load_sut()


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


def test_setup_path_invalid_dir(tmp_path):
    generator = gen.Pynguin(
        configuration=MagicMock(log_file=None, project_path=tmp_path / "nope")
    )
    assert generator._setup_path() is False


def test_setup_path_valid_dir(tmp_path):
    module_name = "test_module"
    generator = gen.Pynguin(
        configuration=MagicMock(
            log_file=None, project_path=tmp_path, module_name=module_name
        )
    )
    with mock.patch("sys.path") as path_mock:
        assert generator._setup_path() is True
        path_mock.insert.assert_called_with(0, tmp_path)


def test_setup_hook():
    module_name = "test_module"
    generator = gen.Pynguin(
        configuration=MagicMock(log_file=None, module_name=module_name)
    )
    with mock.patch.object(gen, "install_import_hook") as hook_mock:
        assert generator._setup_import_hook()
        hook_mock.assert_called_once()


def test_run(tmp_path):
    generator = gen.Pynguin(
        configuration=MagicMock(log_file=None, project_path=tmp_path / "nope")
    )
    with mock.patch.object(gen.Pynguin, "_run") as run_mock:
        generator.run()
        run_mock.assert_called_once()
