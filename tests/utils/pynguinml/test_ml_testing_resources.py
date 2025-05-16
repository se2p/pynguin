#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import json

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import yaml

import pynguin.configuration as config
import pynguin.utils.pynguinml.ml_testing_resources as tr

from pynguin.utils.exceptions import ConstraintValidationError


@pytest.fixture(autouse=True)
def clear_lru_cache():
    # Clear the cache before each test to avoid cross-test pollution
    tr.get_datatype_mapping.cache_clear()
    tr.get_nparray_function.cache_clear()
    tr.get_constructor_function.cache_clear()


@pytest.fixture
def mock_config(monkeypatch):
    def set_mock_paths(**kwargs):
        for attr, value in kwargs.items():
            monkeypatch.setattr(config.configuration.pynguinml, attr, value)

    return set_mock_paths


@pytest.mark.parametrize(
    "file_ext, write_func",
    [
        (".yaml", lambda data: yaml.dump(data)),  # noqa: PLW0108
        (".json", lambda data: json.dumps(data)),  # noqa: PLW0108
    ],
)
def test_get_datatype_mapping_valid_formats(mock_config, tmp_path, file_ext, write_func):
    file_path = tmp_path / f"dtype_mapping{file_ext}"
    shared_content = {
        "torch.int": "int32",
        "torch.float": "float64",
        "torch.uint8": "uint8",
    }
    file_path.write_text(write_func(shared_content))
    mock_config(dtype_mapping_path=str(file_path))

    dtype_map = tr.get_datatype_mapping()
    assert dtype_map == shared_content


def test_get_datatype_mapping_missing_file(mock_config):
    mock_config(dtype_mapping_path="nonexistent_file.yaml")
    dtype_map = tr.get_datatype_mapping()
    assert dtype_map is None


def test_get_datatype_mapping_unsupported_extension(mock_config, tmp_path):
    txt_path = tmp_path / "dtype_mapping.txt"
    txt_path.write_text("Not a valid file")
    mock_config(dtype_mapping_path=str(txt_path))

    dtype_map = tr.get_datatype_mapping()
    assert dtype_map is None


def test_get_datatype_mapping_invalid_dtype(mock_config, tmp_path):
    yaml_path = tmp_path / "dtype_mapping.yaml"
    invalid_yaml_content = {"torch.int": "not_a_dtype"}
    yaml_path.write_text(yaml.dump(invalid_yaml_content))
    mock_config(dtype_mapping_path=str(yaml_path))

    dtype_map = tr.get_datatype_mapping()
    assert dtype_map is None


def test_get_datatype_mapping_empty_path(mock_config):
    mock_config(dtype_mapping_path="")

    dtype_map = tr.get_datatype_mapping()
    assert dtype_map is None


def test_get_nparray_function():
    mock_test_cluster = MagicMock()

    result = tr.get_nparray_function(mock_test_cluster)

    assert result is not None


def test_get_constructor_function_valid(monkeypatch):
    mock_test_cluster = MagicMock()

    monkeypatch.setattr(tr.config.configuration.pynguinml, "constructor_function", "math.sqrt")
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constructor_function_parameter", "x")

    result = tr.get_constructor_function(mock_test_cluster)

    assert result is not None


def test_get_constructor_function_no_config(monkeypatch):
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constructor_function", "")
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constructor_function_parameter", "")

    result = tr.get_constructor_function(MagicMock())

    assert result is None


def test_get_constructor_function_import_error(monkeypatch):
    monkeypatch.setattr(
        tr.config.configuration.pynguinml, "constructor_function", "nonexistent.module"
    )
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constructor_function_parameter", "x")

    result = tr.get_constructor_function(MagicMock())

    assert result is None


def test_load_and_process_constraints_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constraints_path", str(tmp_path))

    result = tr.load_and_process_constraints("dummy_module", "dummy_func", ["param1"])

    assert result == ({}, [])


def test_load_and_process_constraints_unsupported_extension(tmp_path, monkeypatch):
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constraints_path", str(tmp_path))

    file_path = tmp_path / "dummy_module.dummy_func.txt"
    valid_content = {"constraints": {"param1": {"dtype": "float32"}}}
    file_path.write_text(yaml.dump(valid_content))

    result = tr.load_and_process_constraints("dummy_module", "dummy_func", ["param1"])

    assert result == ({}, [])


def test_load_and_process_constraints_malformed_file(tmp_path, monkeypatch):
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constraints_path", str(tmp_path))

    file_path = tmp_path / "dummy_module.dummy_func.yaml"
    file_path.write_text("invalid: [:::")  # Malformed YAML

    result = tr.load_and_process_constraints("dummy_module", "dummy_func", ["param1"])

    assert result == ({}, [])


@pytest.mark.parametrize(
    "file_ext, write_func",
    [
        (".yaml", lambda data: yaml.dump(data)),  # noqa: PLW0108
        (".json", lambda data: json.dumps(data)),  # noqa: PLW0108
    ],
)
def test_load_and_process_constraints_valid(monkeypatch, tmp_path, file_ext, write_func):
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constraints_path", str(tmp_path))

    file_path = tmp_path / f"dummy_module.dummy_func{file_ext}"
    valid_content = {"constraints": {"param1": {"dtype": "float32"}}}
    file_path.write_text(write_func(valid_content))

    with (
        patch.object(tr, "MLParameter", return_value="mock_param") as mock_mlparam,
        patch.object(tr, "_determine_generation_order", return_value=["param1"]),
    ):
        result = tr.load_and_process_constraints("dummy_module", "dummy_func", ["param1"])

    assert result[0] == {"param1": "mock_param"}
    assert result[1] == ["param1"]
    mock_mlparam.assert_called_once()


def test_load_and_process_constraints_parameter_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(tr.config.configuration.pynguinml, "constraints_path", str(tmp_path))

    file_path = tmp_path / "dummy_module.dummy_func.yaml"
    valid_content = {"constraints": {"param1": {"dtype": "float32"}}}
    file_path.write_text(yaml.dump(valid_content))

    with (
        patch.object(tr, "MLParameter", return_value="mock_param"),
        patch.object(tr, "_determine_generation_order", return_value=["param1", "param2"]),
    ):
        result = tr.load_and_process_constraints("dummy_module", "dummy_func", ["param1", "param2"])

    # param2 not in constraints, should be None
    assert result[0] == {"param1": "mock_param", "param2": None}
    assert result[1] == ["param1", "param2"]


def test_determine_generation_order_no_dependencies_and_none():
    parameters = {
        "A": MagicMock(var_dep=[], parameter_dependencies={}),
        "B": None,
    }

    result = tr._determine_generation_order(parameters)
    # Since no dependencies, any order is fine (we check set equality)
    assert set(result) == {"A", "B"}


def test_determine_generation_order_simple_dependency():
    a = MagicMock(var_dep=["B"], parameter_dependencies={})
    b = MagicMock(var_dep=[], parameter_dependencies={})
    parameters = {"A": a, "B": b}

    result = tr._determine_generation_order(parameters)
    assert result == ["B", "A"]
    assert a.parameter_dependencies["B"] is b


def test_determine_generation_order_self_dependency():
    a = MagicMock(var_dep=["A"], parameter_dependencies={})
    parameters = {"A": a}

    with pytest.raises(ConstraintValidationError, match="Parameter A has dependency on it self."):  # noqa: RUF043
        tr._determine_generation_order(parameters)


def test_determine_generation_order_dependency_not_exist():
    a = MagicMock(var_dep=["B"], parameter_dependencies={})
    parameters = {"A": a}

    with pytest.raises(
        ConstraintValidationError,
        match="Dependency B does not exist in parameters.",  # noqa: RUF043
    ):
        tr._determine_generation_order(parameters)


def test_determine_generation_order_dependency_object_none():
    a = MagicMock(var_dep=["B"], parameter_dependencies={})
    parameters = {"A": a, "B": None}

    with pytest.raises(
        ConstraintValidationError,
        match="Dependency object for parameter B is None.",  # noqa: RUF043
    ):
        tr._determine_generation_order(parameters)


def test_determine_generation_order_cycle():
    # A depends on B, B depends on A -> cycle
    a = MagicMock(var_dep=["B"], parameter_dependencies={})
    b = MagicMock(var_dep=["A"], parameter_dependencies={})
    parameters = {"A": a, "B": b}

    with pytest.raises(ConstraintValidationError, match="Could not generate generation order:"):
        tr._determine_generation_order(parameters)
