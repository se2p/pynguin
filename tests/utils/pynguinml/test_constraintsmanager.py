#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest
import yaml

import pynguin.configuration as config

from pynguin.utils.exceptions import ConstraintValidationError
from pynguin.utils.pynguinml.constraintsmanager import ConstraintsManager


@pytest.fixture
def mock_config(monkeypatch):
    def set_mock_paths(**kwargs):
        for attr, value in kwargs.items():
            monkeypatch.setattr(config.configuration.pynguinml, attr, value)

    return set_mock_paths


def test_singleton_behavior():
    instance1 = ConstraintsManager()
    instance2 = ConstraintsManager()

    assert instance1 is instance2, "ConstraintsManager is not a singleton!"


def test_ml_testing_enabled_valid_path(mock_config, tmp_path):
    valid_path = tmp_path / "valid_constraints"
    valid_path.mkdir()  # Simulate a valid directory

    mock_config(constraints_path=str(valid_path))

    ConstraintsManager()._initialized = False
    manager = ConstraintsManager()
    assert manager.ml_testing_enabled(), "ML testing should be enabled for a valid constraints path"


def test_ml_testing_disabled_invalid_path(mock_config):
    mock_config(constraints_path="")  # Empty path
    ConstraintsManager()._initialized = False
    manager = ConstraintsManager()
    assert not manager.ml_testing_enabled(), (
        "ML testing should be disabled for an empty constraints path"
    )

    mock_config(constraints_path="/invalid/path/does_not_exist")  # Non-existent path
    ConstraintsManager()._initialized = False
    manager = ConstraintsManager()
    assert not manager.ml_testing_enabled(), (
        "ML testing should be disabled for a non-existent constraints path"
    )


def test_load_dtype_map_valid_yaml(mock_config, tmp_path):
    yaml_path = tmp_path / "dtype_mapping.yaml"

    # Sample valid YAML content
    valid_yaml_content = {
        "torch.int": "int32",
        "torch.float": "float64",
        "torch.uint8": "uint8",
    }

    yaml_path.write_text(yaml.dump(valid_yaml_content))
    mock_config(dtype_mapping_path=str(yaml_path))

    ConstraintsManager()._initialized = False
    manager = ConstraintsManager()

    dtype_map = manager._load_dtype_map()
    assert dtype_map == valid_yaml_content, "The dtype map should match the valid YAML content"


def test_load_dtype_map_invalid_yaml(mock_config, tmp_path):
    yaml_path = tmp_path / "dtype_mapping.yaml"

    # Sample valid YAML content
    valid_yaml_content = {
        "torch.uint8": "foo",
    }

    yaml_path.write_text(yaml.dump(valid_yaml_content))
    mock_config(dtype_mapping_path=str(yaml_path))

    manager = ConstraintsManager()

    assert manager._load_dtype_map() == {}, (
        "The dtype map should be empty when the YAML file is invalid"
    )


def test_load_and_process_constraints_valid(mock_config, tmp_path):
    constraints_path = tmp_path / "testmodule.testfunction.yaml"

    valid_constraints = {
        "constraints": {
            "input1": {"ndim": ["ndim:&input2"], "tensor_t": ["torch.tensor"]},
            "input2": {"default": None, "ndim": ["4"], "tensor_t": ["torch.tensor"]},
            "input3": {},
        }
    }

    constraints_path.write_text(yaml.dump(valid_constraints))

    mock_config(constraints_path=str(tmp_path))

    ConstraintsManager()._initialized = False
    manager = ConstraintsManager()

    parameters, generation_order = manager.load_and_process_constraints(
        "testmodule", "testfunction", ["input1", "input2", "input3"]
    )

    assert parameters["input1"] is not None
    assert parameters["input2"] is not None
    assert parameters["input3"] is None
    assert generation_order[0] == "input2"


def test_load_and_process_constraints_invalid(mock_config, tmp_path):
    constraints_path = tmp_path / "testmodule.testfunction.yaml"

    valid_constraints = {
        "constraints": {
            "input1": {"ndim": ["ndim:&input3"], "tensor_t": ["torch.tensor"]},
            "input2": {},
        }
    }

    constraints_path.write_text(yaml.dump(valid_constraints))

    mock_config(constraints_path=str(tmp_path))

    ConstraintsManager()._initialized = False
    manager = ConstraintsManager()

    with pytest.raises(ConstraintValidationError):
        manager.load_and_process_constraints(
            "testmodule", "testfunction", ["input1", "input2", "input3"]
        )
