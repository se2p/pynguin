#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the libcst-backed ML test generation.

Covers the value<->CST round-trip helpers (:mod:`pynguin.utils.pynguinml.ndarray_cst`),
the shape-aware nested-list mutation operators
(:mod:`pynguin.utils.pynguinml.ndarray_mutation`), and the statement-chain emission
of :class:`pynguin.testcase.testfactory.MLTestFactory`.
"""

from __future__ import annotations

from inspect import Parameter, Signature
from unittest.mock import MagicMock

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
import pynguin.utils.pynguinml.ml_parsing_utils as mlpu
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import MLCallableData, ModuleTestCluster
from pynguin.analyses.typesystem import AnyType, InferredSignature, TypeSystem
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.pynguinml import ndarray_cst, ndarray_mutation, np_rng
from pynguin.utils.pynguinml.mlparameter import MLParameter
from tests.testcase._builders import make_test_case, stmt


@pytest.fixture(autouse=True)
def _seeded_rngs():
    randomness.RNG.seed(42)
    np_rng.init_rng(42)


# ---------------------------------------------------------------------------
# ndarray_cst round-trips
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        0,
        42,
        -17,
        1.5,
        -2.25,
        True,
        False,
        None,
        "hello",
        complex(1.5, 2.0),
        complex(-1.5, -2.0),
        complex(0.0, 2.0),
        [1, 2, 3],
        [-1, 0, 7],
        [[1, 2], [3, 4]],
        [[[1.5, -2.5]], [[0.0, 3.25]]],
        [True, False, True],
        [complex(1.0, -2.0), complex(-3.5, 4.5)],
        ["a", "b"],
        (1, 2),
        (1,),
        (-1.5, 2.5),
        [],
        [[], []],
    ],
)
def test_ml_value_cst_round_trip(value):
    expr = ndarray_cst.ml_value_to_cst(value)
    assert ndarray_cst.ml_cst_to_value(expr) == value


def test_ml_value_to_cst_rejects_unsupported():
    with pytest.raises(ValueError, match="Unsupported value type"):
        ndarray_cst.ml_value_to_cst(object())


def test_ml_cst_to_value_rejects_unsupported():
    with pytest.raises(ValueError, match="Unsupported"):
        ndarray_cst.ml_cst_to_value(cst.parse_expression("foo(1)"))
    with pytest.raises(ValueError, match="Unsupported CST node"):
        ndarray_cst.ml_cst_to_value(cst.parse_expression("{1: 2}"))


def test_ml_value_to_cst_renders_parseable_code():
    value = [[1, -2], [3, 4]]
    expr = ndarray_cst.ml_value_to_cst(value)
    code = cst.Module(body=[]).code_for_node(expr)
    assert code == "[[1, -2], [3, 4]]"


# ---------------------------------------------------------------------------
# ndarray_mutation
# ---------------------------------------------------------------------------


def _is_rectangular(elements):
    """Check that a nested list is rectangular by computing its shape."""
    shape = mlpu.get_shape(elements)
    return shape is not None


def test_random_deletion_keeps_valid_shape():
    for _ in range(20):
        elements = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
        mutated, changed = ndarray_mutation.random_deletion(elements)
        assert _is_rectangular(mutated)
        if changed:
            assert mutated != [[1, 2, 3], [4, 5, 6], [7, 8, 9]]


def test_random_replacement_respects_dtype_kind():
    changed_once = False
    for _ in range(20):
        elements = [[1, 2], [3, 4]]
        mutated, changed = ndarray_mutation.random_replacement(elements, "int32", 0, 10)
        assert _is_rectangular(mutated)
        for row in mutated:
            for leaf in row:
                assert isinstance(leaf, int)
                assert 0 <= leaf <= 10
        changed_once |= changed
    assert changed_once


def test_random_insertion_keeps_rectangularity():
    changed_once = False
    for _ in range(20):
        elements = [[1, 2], [3, 4]]
        mutated, changed = ndarray_mutation.random_insertion(elements, "int32", 0, 10)
        assert _is_rectangular(mutated)
        changed_once |= changed
    assert changed_once


def test_mutate_ndarray_combined():
    config.configuration.search_algorithm.test_delete_probability = 1.0
    config.configuration.search_algorithm.test_change_probability = 1.0
    config.configuration.search_algorithm.test_insert_probability = 1.0
    changed_once = False
    for _ in range(20):
        elements = [[1, 2, 3], [4, 5, 6]]
        mutated, changed = ndarray_mutation.mutate_ndarray(elements, "int32", 0, 10)
        assert _is_rectangular(mutated)
        changed_once |= changed
    assert changed_once


def test_replacement_value_kinds():
    assert isinstance(ndarray_mutation.replacement_value("int32", 0, 10), int)
    assert isinstance(ndarray_mutation.replacement_value("float64", 0.0, 1.0), float)
    assert isinstance(ndarray_mutation.replacement_value("complex128", 0.0, 1.0), complex)
    assert isinstance(ndarray_mutation.replacement_value("bool", 0, 0), bool)


# ---------------------------------------------------------------------------
# MLTestFactory
# ---------------------------------------------------------------------------


def _sut_function(x):
    return x


def _make_ml_factory(param: MLParameter):
    """Build an MLTestFactory over a mock cluster with constraint data for ``x``."""
    type_system = TypeSystem()
    signature = InferredSignature(
        signature=Signature(parameters=[Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)]),
        original_return_type=AnyType(),
        original_parameters={"x": AnyType()},
        type_system=type_system,
    )
    accessible = GenericFunction(_sut_function, signature, set(), "_sut_function")

    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_ml_data_for.return_value = MLCallableData(
        parameters={"x": param},
        generation_order=["x"],
    )
    factory = tf.MLTestFactory(cluster, EmptyConstantProvider())
    return factory, accessible


def _int32_matrix_param() -> MLParameter:
    return MLParameter(
        "x",
        {"ndim": [2], "dtype": ["int32"], "range": ["[0,10]"]},
        None,
    )


def test_ml_factory_emits_ndarray_chain():
    config.configuration.pynguinml.ignore_constraints_probability = 0.0
    factory, accessible = _make_ml_factory(_int32_matrix_param())

    test_case = tc.TestCase()
    position = factory.append_generic_accessible(test_case, accessible)

    assert position == 3
    assert test_case.size() == 4

    ndarray_stmt = test_case.get_statement(0)
    assert ndarray_stmt.ml_info is not None
    assert ndarray_stmt.ml_info.kind == "ndarray"
    assert ndarray_stmt.ml_info.dtype == "int32"
    assert ndarray_stmt.bound_type is None

    dtype_stmt = test_case.get_statement(1)
    assert dtype_stmt.ml_info is not None
    assert dtype_stmt.ml_info.kind == "allowed_values"
    assert dtype_stmt.ml_info.allowed_values == ["int32"]

    call_stmt = test_case.get_statement(2)
    assert call_stmt.ml_info is not None
    assert call_stmt.ml_info.kind == "ml_call"
    assert call_stmt.accessible is not None

    sut_stmt = test_case.get_statement(3)
    assert sut_stmt.ml_info is None
    assert sut_stmt.accessible is accessible

    code = test_case.to_code()
    assert "np.array(" in code
    assert "object = var_0" in code
    assert "dtype = var_1" in code
    assert "_sut_function(x = var_2)" in code

    # The rendered ndarray literal round-trips to a rectangular int matrix.
    value = ndarray_cst.ml_cst_to_value(ndarray_stmt.node.body[0].value)
    assert isinstance(value, list)
    assert _is_rectangular(value)
    assert len(mlpu.get_shape(value)) == 2


def test_ml_factory_mutate_value_never_touches_ml_call():
    config.configuration.pynguinml.ignore_constraints_probability = 0.0
    factory, accessible = _make_ml_factory(_int32_matrix_param())
    test_case = tc.TestCase()
    factory.append_generic_accessible(test_case, accessible)

    assert test_case.get_statement(2).ml_info.kind == "ml_call"
    assert factory.mutate_value(test_case, 2) is False


def test_ml_factory_mutate_call_and_change_random_call_refuse_ml():
    config.configuration.pynguinml.ignore_constraints_probability = 0.0
    factory, accessible = _make_ml_factory(_int32_matrix_param())
    test_case = tc.TestCase()
    factory.append_generic_accessible(test_case, accessible)

    for position in range(3):
        assert factory.mutate_call(test_case, position) is False
        assert factory.change_random_call(test_case, position) is False


def test_ml_factory_clone_preserves_ml_info():
    config.configuration.pynguinml.ignore_constraints_probability = 0.0
    factory, accessible = _make_ml_factory(_int32_matrix_param())
    test_case = tc.TestCase()
    factory.append_generic_accessible(test_case, accessible)

    clone = test_case.clone()
    assert clone.size() == test_case.size()
    for original, copied in zip(test_case.statements(), clone.statements(), strict=True):
        assert copied.ml_info == original.ml_info


def test_ml_factory_append_statement_refuses_ml_statements():
    factory, _ = _make_ml_factory(_int32_matrix_param())
    test_case = tc.TestCase()
    ml_statement = tc.Statement(
        node=stmt("var_0 = [1, 2]").node,
        bound_variable="var_0",
        ml_info=tc.MLStatementInfo(kind="ndarray", dtype="int32", low=0.0, high=10.0),
    )
    factory.append_statement(test_case, ml_statement)
    assert test_case.size() == 0

    plain = stmt("var_0 = 42", bound_variable="var_0", bound_type=int)
    factory.append_statement(test_case, plain)
    assert test_case.size() == 1


def test_ml_factory_mutate_value_allowed_values():
    factory, _ = _make_ml_factory(_int32_matrix_param())
    statement = tc.Statement(
        node=stmt("var_0 = 'a'").node,
        bound_variable="var_0",
        ml_info=tc.MLStatementInfo(kind="allowed_values", allowed_values=["a", "b", "c"]),
    )
    test_case = make_test_case(statement)

    assert factory.mutate_value(test_case, 0) is True
    mutated = test_case.get_statement(0)
    assert mutated.ml_info == statement.ml_info
    value = ndarray_cst.ml_cst_to_value(mutated.node.body[0].value)
    assert value in {"a", "b", "c"}


def test_ml_factory_mutate_value_allowed_values_single_option():
    factory, _ = _make_ml_factory(_int32_matrix_param())
    statement = tc.Statement(
        node=stmt("var_0 = 'int32'").node,
        bound_variable="var_0",
        ml_info=tc.MLStatementInfo(kind="allowed_values", allowed_values=["int32"]),
    )
    test_case = make_test_case(statement)
    assert factory.mutate_value(test_case, 0) is False


def test_ml_factory_mutate_value_ml_scalar():
    factory, _ = _make_ml_factory(_int32_matrix_param())
    statement = tc.Statement(
        node=stmt("var_0 = 5").node,
        bound_variable="var_0",
        bound_type=int,
        ml_info=tc.MLStatementInfo(kind="ml_scalar", dtype="int32", low=0.0, high=10.0),
    )
    test_case = make_test_case(statement)

    assert factory.mutate_value(test_case, 0) is True
    value = ndarray_cst.ml_cst_to_value(test_case.get_statement(0).node.body[0].value)
    assert isinstance(value, int)
    assert 0 <= value <= 10


def test_ml_factory_mutate_value_ndarray_keeps_shape_and_dtype():
    config.configuration.search_algorithm.test_delete_probability = 0.0
    config.configuration.search_algorithm.test_change_probability = 1.0
    config.configuration.search_algorithm.test_insert_probability = 0.0
    factory, _ = _make_ml_factory(_int32_matrix_param())

    mutated_once = False
    for _ in range(30):
        statement = tc.Statement(
            node=stmt("var_0 = [[1, 2], [3, 4]]").node,
            bound_variable="var_0",
            ml_info=tc.MLStatementInfo(kind="ndarray", dtype="int32", low=0.0, high=10.0),
        )
        test_case = make_test_case(statement)
        if factory.mutate_value(test_case, 0):
            mutated_once = True
            value = ndarray_cst.ml_cst_to_value(test_case.get_statement(0).node.body[0].value)
            assert _is_rectangular(value)
            for row in value:
                for leaf in row:
                    assert isinstance(leaf, int)
                    assert 0 <= leaf <= 10
    assert mutated_once


def test_ml_factory_falls_back_without_ml_data():
    """Without constraint data the base generation path is used."""
    type_system = TypeSystem()
    signature = InferredSignature(
        signature=Signature(parameters=[Parameter("x", Parameter.POSITIONAL_OR_KEYWORD)]),
        original_return_type=AnyType(),
        original_parameters={"x": AnyType()},
        type_system=type_system,
    )
    accessible = GenericFunction(_sut_function, signature, set(), "_sut_function")
    cluster = MagicMock(ModuleTestCluster)
    cluster.type_system = type_system
    cluster.get_ml_data_for.return_value = None
    factory = tf.MLTestFactory(cluster, EmptyConstantProvider())

    test_case = tc.TestCase()
    position = factory.append_generic_accessible(test_case, accessible)
    assert position >= 0
    assert all(statement.ml_info is None for statement in test_case.statements())
