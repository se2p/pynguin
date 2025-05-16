#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock
from unittest.mock import patch

import numpy as np
import pytest

import pynguin.testcase.statement as stmt
import pynguin.utils.pynguinml.ml_testfactory_utils as mltu

from pynguin.analyses.typesystem import AnyType
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.pynguinml import np_rng
from pynguin.utils.pynguinml.mlparameter import MLParameter
from pynguin.utils.pynguinml.mlparameter import Range


def test_select_dtype():
    # The data is already validated beforehand by MLParameter
    mock_param = MagicMock(spec=MLParameter)
    mock_param.valid_dtypes = []
    mock_param.tensor_expected = False

    selected_dtype = mltu.select_dtype(mock_param)

    assert selected_dtype == "None"

    mock_param.valid_dtypes = ["int32", "float64", "bool"]
    mock_param.tensor_expected = False

    selected_dtype = mltu.select_dtype(mock_param)

    assert selected_dtype in mock_param.valid_dtypes

    mock_param2 = MagicMock(spec=MLParameter)
    mock_param2.current_data = np.array([1, 2, 3], dtype="int32")

    mock_param.parameter_dependencies = {"param2": mock_param2}
    mock_param.valid_dtypes = ["dtype:&param2"]

    selected_dtype = mltu.select_dtype(mock_param)

    assert selected_dtype == "int32"

    mock_param2.current_data = 5

    selected_dtype = mltu.select_dtype(mock_param)

    assert selected_dtype == "int"


def test_select_ndim():
    # The data is already validated beforehand by MLParameter
    mock_param = MagicMock(spec=MLParameter)
    mock_param.tensor_expected = False

    # special case for str
    selected_ndim = mltu.select_ndim(mock_param, "str")
    assert selected_ndim == 0

    # no valid ndims, so one chosen randomly
    mock_param.valid_ndims = []
    selected_ndim = mltu.select_ndim(mock_param, "")
    assert selected_ndim in {0, 1, 2, 3, 4}

    # list of valid ndims
    mock_param.valid_ndims = ["0", "1", "2"]
    selected_ndim = mltu.select_ndim(mock_param, "")
    assert selected_ndim in map(int, mock_param.valid_ndims)

    # var dependency
    mock_param2 = MagicMock(spec=MLParameter)
    mock_param.parameter_dependencies = {"param2": mock_param2}
    mock_param.valid_ndims = ["ndim:&param2"]

    # "ndim:" dependency with ndarray
    mock_param2.current_data = np.array([[2], [2]])
    selected_ndim = mltu.select_ndim(mock_param, "")
    assert selected_ndim == 2

    # "ndim:" dependency with scalar
    mock_param2.current_data = 5
    selected_ndim = mltu.select_ndim(mock_param, "")
    assert selected_ndim == 0

    # "ndim:" dependency with faulty value
    mock_param2.current_data = [1, 2, 3]  # should be either ndarray or scalar
    with pytest.raises(ConstructionFailedException):
        mltu.select_ndim(mock_param, "")

    # "standard" dependency with wrong type (bool)
    mock_param.valid_ndims = ["&param2"]
    mock_param2.current_data = True
    with pytest.raises(ConstructionFailedException):
        mltu.select_ndim(mock_param, "")

    # "standard" dependency with wrong type (not int nor float)
    mock_param2.current_data = None
    with pytest.raises(ConstructionFailedException):
        mltu.select_ndim(mock_param, "")

    # "standard" dependency with correct type
    mock_param2.current_data = 5
    selected_ndim = mltu.select_ndim(mock_param, "")
    assert selected_ndim == 5

    # const dependency
    mock_param.valid_ndims = ["batch_size"]
    selected_ndim = mltu.select_ndim(mock_param, "")
    assert isinstance(selected_ndim, int)
    assert isinstance(mltu.ml_constant_pool.get_value("batch_size"), int)


def test_generate_shape():  # noqa: PLR0915
    mock_param = MagicMock(spec=MLParameter)

    # no valid shapes, so one chosen randomly
    mock_param.valid_shapes = []
    generated_shape = mltu.generate_shape(mock_param, 3)
    assert isinstance(generated_shape, list)
    assert len(generated_shape) == 3

    mock_param.valid_shapes = ["dummy_shape"]
    # Patch _select_shape_constraint to return None explicitly
    with patch.object(mltu, "_select_shape_constraint", return_value=None):
        generated_shape = mltu.generate_shape(mock_param, 3)
    assert isinstance(generated_shape, list)
    assert len(generated_shape) == 3

    # normal valid shape
    mock_param.valid_shapes = ["1,2,3"]
    generated_shape = mltu.generate_shape(mock_param, 3)
    assert generated_shape == [1, 2, 3]

    # shape with unknown dimensions
    mock_param.valid_shapes = ["...,2,2"]
    generated_shape = mltu.generate_shape(mock_param, 4)
    assert len(generated_shape) in {2, 3, 4}

    # shape with bounds
    mock_param.valid_shapes = [">=2,<1,>3"]
    generated_shape = mltu.generate_shape(mock_param, 3)
    assert generated_shape in [[2, 0, 4], [3, 0, 4], [4, 0, 4]]

    mock_param2 = MagicMock(spec=MLParameter)
    mock_param.parameter_dependencies = {"param2": mock_param2}

    # "len:" dependency
    mock_param.valid_shapes = ["len:&param2,len:&param2+2"]
    mock_param2.current_data = np.array([1, 2])
    generated_shape = mltu.generate_shape(mock_param, 2)
    assert generated_shape == [2, 4]
    # "len:" dependency but wrong type
    mock_param2.current_data = 42
    with pytest.raises(ConstructionFailedException):
        mltu.generate_shape(mock_param, 2)

    # "ndim:" dependency
    mock_param.valid_shapes = ["ndim:param2,ndim:param2-0"]
    # ndarray
    mock_param2.current_data = np.array([1, 2])
    generated_shape = mltu.generate_shape(mock_param, 2)
    assert generated_shape == [1, 1]
    # scalar
    mock_param2.current_data = 42
    generated_shape = mltu.generate_shape(mock_param, 2)
    assert generated_shape == [0, 0]
    # wrong type
    mock_param2.current_data = [1, 2, 3]
    with pytest.raises(ConstructionFailedException):
        mltu.generate_shape(mock_param, 2)

    # "max_value:" dependency
    mock_param.valid_shapes = ["max_value:&param2,max_value:&param2/3"]
    # valid max_value
    mock_param2.current_data = np.array([1, 2, 3])
    generated_shape = mltu.generate_shape(mock_param, 2)
    assert generated_shape == [3, 1]
    # invalid max_value
    mock_param2.current_data = 42
    with pytest.raises(ConstructionFailedException):
        mltu.generate_shape(mock_param, 2)

    # "shape:" dependency
    mock_param.valid_shapes = ["shape:&param2"]
    # ndarray
    mock_param2.current_data = np.array([[2, 2], [3, 3]])
    generated_shape = mltu.generate_shape(mock_param, 3)
    assert generated_shape == [2, 2]
    # scalar
    mock_param2.current_data = 42
    generated_shape = mltu.generate_shape(mock_param, 3)
    assert generated_shape == []
    # wrong type
    mock_param2.current_data = [1, 2, 3]
    with pytest.raises(ConstructionFailedException):
        mltu.generate_shape(mock_param, 3)

    # "standard" dependency
    mock_param.valid_shapes = ["&param2,&param2*2"]
    # wrong type (bool)
    mock_param2.current_data = True
    with pytest.raises(ConstructionFailedException):
        mltu.generate_shape(mock_param, 2)
    # wrong type (not int nor float)
    mock_param2.current_data = None
    with pytest.raises(ConstructionFailedException):
        mltu.generate_shape(mock_param, 2)
    # correct type
    mock_param2.current_data = 2.8
    generated_shape = mltu.generate_shape(mock_param, 2)
    assert generated_shape == [2, 4]

    # const dependency
    mock_param.valid_shapes = ["batch_size,num_labels"]
    generated_shape = mltu.generate_shape(mock_param, 2)
    assert len(generated_shape) == 2
    assert isinstance(mltu.ml_constant_pool.get_value("batch_size"), int)
    assert isinstance(mltu.ml_constant_pool.get_value("num_labels"), int)


def test_select_shape_constraint_returns_none():
    # Setup: no "...", no ":", wrong ndim
    mock_param = MagicMock(spec=MLParameter)
    mock_param.valid_shapes = ["1,2"]  # len=2

    result = mltu._select_shape_constraint(mock_param, selected_ndim=3)

    assert result is None


def test__get_range():
    mock_param = MagicMock(spec=MLParameter)

    # default values
    mock_param.valid_ranges = []
    low, high = mltu._get_range(mock_param, "int32")
    assert low == -2048
    assert high == 2048

    # too big range, choose default
    mock_param.valid_ranges = [Range("int32", -10000, 10000)]
    low, high = mltu._get_range(mock_param, "int32")
    assert low == -2048
    assert high == 2048

    # choose range
    mock_param.valid_ranges = [Range(None, -100, 100)]
    low, high = mltu._get_range(mock_param, "int32")
    assert low == -100
    assert high == 100

    # uint should have 0 as lower bound
    mock_param.valid_ranges = [Range(None, -100, 100)]
    low, high = mltu._get_range(mock_param, "uint32")
    assert low == 0
    assert high == 100

    # Range has negative high (-10), which would make `high = max(-10, 0)` → 0
    mock_param.valid_ranges = [Range(None, -100, -10)]
    low, high = mltu._get_range(mock_param, "uint32")
    assert low == 0
    assert high == 0


def test_generate_ndarray():
    np_rng.NP_RNG = np.random.default_rng()

    mock_param = MagicMock(spec=MLParameter)
    mock_param.valid_ranges = [Range(None, -100, 100)]

    # invalid datatype
    with pytest.raises(ConstructionFailedException):
        mltu.generate_ndarray(mock_param, [2, 2], "invalid_dtype")

    # generate int
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [2, 2], "int32")
    assert isinstance(ndarray[0][0], int)
    assert np.array(ndarray).shape == (2, 2)

    # generate float
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [3, 3], "float32")
    assert isinstance(ndarray[0][0], float)
    assert np.array(ndarray).shape == (3, 3)

    # generate complex
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [1, 1], "complex64")
    assert isinstance(ndarray[0][0], complex)
    assert np.array(ndarray).shape == (1, 1)

    # generate bool
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [1, 2], "bool")
    assert isinstance(ndarray[0][0], bool)
    assert np.array(ndarray).shape == (1, 2)


def test_generate_ndarray_empty_shape():
    np_rng.NP_RNG = np.random.default_rng()

    mock_param = MagicMock(spec=MLParameter)
    mock_param.valid_ranges = [Range(None, -100, 100)]

    # invalid datatype
    with pytest.raises(ConstructionFailedException):
        mltu.generate_ndarray(mock_param, [], "invalid_dtype")

    # generate int
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [], "int32")
    assert isinstance(ndarray, int)

    # generate float
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [], "float32")
    assert isinstance(ndarray, float)

    # generate complex
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [], "complex64")
    assert isinstance(ndarray, complex)

    # generate bool
    ndarray, _, _ = mltu.generate_ndarray(mock_param, [], "bool")
    assert isinstance(ndarray, bool)


def test_change_generation_order():
    generation_order = ["c", "b", "e", "a"]
    param_types = {
        "a": AnyType(),
        "b": AnyType(),
        "c": AnyType(),
        "d": AnyType(),
        "e": AnyType(),
    }

    sorted_params = mltu.change_generation_order(generation_order, param_types)

    # "d" is missing in generation_order, so it should be at the end
    assert list(sorted_params.keys()) == ["c", "b", "e", "a", "d"]


def test_reset_parameter_objects():
    param1 = MagicMock(spec=MLParameter)
    param1.current_data = "dummy"
    param2 = MagicMock(spec=MLParameter)
    param2.current_data = "dummy"

    params = {"param1": param1, "param2": param2, "param_none": None}

    # Patch the constant pool reset
    with patch.object(mltu.ml_constant_pool, "reset") as mock_reset:
        mltu.reset_parameter_objects(params)

    assert param1.current_data is None
    assert param2.current_data is None

    # Ensure constant pool reset was called
    mock_reset.assert_called_once()


def test_is_ml_statement():
    mock_stmt = MagicMock(spec=stmt.FunctionStatement)
    mock_stmt.should_mutate = False
    assert mltu.is_ml_statement(mock_stmt) is True

    mock_stmt = MagicMock(spec=stmt.FunctionStatement)
    mock_stmt.should_mutate = True
    assert mltu.is_ml_statement(mock_stmt) is False

    mock_stmt = MagicMock(spec=stmt.NdArrayStatement)
    assert mltu.is_ml_statement(mock_stmt) is True

    mock_stmt = MagicMock(spec=stmt.AllowedValuesStatement)
    assert mltu.is_ml_statement(mock_stmt) is True

    mock_stmt = MagicMock(spec=stmt.ListStatement)
    assert mltu.is_ml_statement(mock_stmt) is False
