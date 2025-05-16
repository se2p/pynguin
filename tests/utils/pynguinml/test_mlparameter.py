#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.utils.exceptions import ConstraintValidationError
from pynguin.utils.pynguinml.mlparameter import MLParameter
from pynguin.utils.pynguinml.mlparameter import Range


@pytest.fixture
def dtype_map():
    return {
        "torch.float32": "float32",
        "torch.float64": "float64",
        "torch.int32": "int32",
        "torch.int64": "int64",
    }


def test_mlparameter_parse_ndims_valid(dtype_map):
    constraints = {"ndim": [2, 3]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert set(param.valid_ndims) == {"2", "3"}

    constraints = {"ndim": [">3", "<=2"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert set(param.valid_ndims) == {"0", "1", "2", "4"}

    constraints = {"ndim": [">=3", "<2"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert set(param.valid_ndims) == {"4", "3", "1", "0"}

    constraints = {"ndim": ["batch_size", "ndim:&param2", "&param3"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert set(param.valid_ndims) == {"batch_size", "ndim:&param2", "&param3"}


def test_mlparameter_parse_ndims_invalid(dtype_map):
    constraints = {"ndim": 2}
    with pytest.raises(ConstraintValidationError):
        MLParameter("test_param", constraints, dtype_map)

    constraints = {"ndim": ["?", "-2", "2.5", "<-2", ">=6", ">random"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_ndims == []

    constraints = {"ndim": ["ndim:param2"]}
    with pytest.raises(ConstraintValidationError):
        MLParameter("test_param", constraints, dtype_map)


def test_mlparameter_parse_shape_valid(dtype_map):
    constraints = {
        "shape": [
            "[1   ,2   ,3]",
            "[..., 2]",
            "[>2,<=&param2,&param3]",
            "[len:&a,ndim:&b,max_value:&c]",
            "shape:&param4",
            "[batch_size,num_labels]",
        ]
    }
    param = MLParameter("test_param", constraints, dtype_map)
    assert set(param.valid_shapes) == {
        "1,2,3",
        "...,2",
        ">2,<=&param2,&param3",
        "len:&a,ndim:&b,max_value:&c",
        "shape:&param4",
        "batch_size,num_labels",
    }


def test_mlparameter_parse_shape_invalid(dtype_map):
    constraints = {"shape": "[1,2,3]"}
    with pytest.raises(ConstraintValidationError):
        MLParameter("test_param", constraints, dtype_map)

    constraints = {
        "shape": [1, "", "[1,2,]", "len:a", "ndim:b", "max_value:c", "shape:d", "[0.5,0.5]"]
    }
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_shapes == []


def test_mlparameter_parse_range_valid(dtype_map):
    constraints = {"range": ["int:[0, inf)", "(1,2]", "(0.0,5]", "[1,2)", "[0.5,5.0)"]}

    expected_ranges = [
        Range(required_dtype="int", lower_bound=0, upper_bound=float("inf")),
        Range(required_dtype=None, lower_bound=2, upper_bound=2),
        Range(required_dtype=None, lower_bound=1e-08, upper_bound=5),
        Range(required_dtype=None, lower_bound=1, upper_bound=1),
        Range(required_dtype=None, lower_bound=0.5, upper_bound=4.99999999),
    ]

    param = MLParameter("test_param", constraints, dtype_map)
    assert len(param.valid_ranges) == len(expected_ranges)
    for range_ in param.valid_ranges:
        assert range_ in expected_ranges


def test_mlparameter_parse_range_invalid(dtype_map):
    # not a list
    constraints = {"range": "[0,inf)"}
    with pytest.raises(ConstraintValidationError):
        MLParameter("test_param", constraints, dtype_map)

    # not strings
    constraints = {"range": [0, 2]}
    with pytest.raises(ConstraintValidationError):
        MLParameter("test_param", constraints, dtype_map)

    constraints = {"range": ["1,5", "[a,2]", "[2,a]", "[5,2]", "(1,1)"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_shapes == []


def test_mlparameter_parse_enum(dtype_map):
    constraints = {"enum": ["foo", "bar"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_enum_values == ["foo", "bar"]

    constraints = {}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_enum_values == []


def test_mlparameter_parse_tensor_t(dtype_map):
    constraints = {"tensor_t": ["random"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.tensor_expected

    constraints = {}
    param = MLParameter("test_param", constraints, dtype_map)
    assert not param.tensor_expected


def test_mlparameter_parse_structure(dtype_map):
    constraints = {"structure": ["list"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.structure == "list"

    constraints = {"structure": ["tuple"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.structure == "tuple"

    constraints = {}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.structure is None

    constraints = {"structure": "list"}
    with pytest.raises(ConstraintValidationError):
        MLParameter("test_param", constraints, dtype_map)


def test_mlparameter_parse_dtype_valid(dtype_map):
    constraints = {
        "dtype": [
            "string",
            "torch.int32",
            "torch.float64",
            "torch.float32",
            "int",
            "float",
            "dtype:&param2",
            "unknown",
            "numeric",
            "tensorshape",
            "scalar",
        ]
    }
    param = MLParameter("test_param", constraints, dtype_map)
    assert set(param.valid_dtypes) == {
        "str",
        "int32",
        "float64",
        "float32",
        "dtype:&param2",
        "int64",
    }


def test_mlparameter_parse_dtype_invalid(dtype_map):
    # no list, so defaults
    constraints = {"dtype": "int"}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_dtypes == list(set(dtype_map.values()))

    # invalid dependency
    constraints = {"dtype": ["dtype:param2"]}
    with pytest.raises(ConstraintValidationError):
        MLParameter("test_param", constraints, dtype_map)

    # constraint is None
    constraints = {"dtype": None}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_dtypes == list(set(dtype_map.values()))

    # only unknown dtypes
    constraints = {"dtype": ["unknown1", "unknown2"]}
    param = MLParameter("test_param", constraints, dtype_map)
    assert param.valid_dtypes == list(set(dtype_map.values()))
