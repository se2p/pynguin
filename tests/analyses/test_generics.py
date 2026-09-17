# This file is part of the Pynguin automated unit test generation framework.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Tests for the pynguin.analyses.generics module."""

from __future__ import annotations

import inspect
import typing
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.analyses import generics
from pynguin.analyses.module import CallableData, ModuleTestCluster
from pynguin.analyses.typesystem import (
    ANY,
    InferredSignature,
    Instance,
    NoneType,
    ProperType,
    TypeSystem,
    TypeVarType,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)


@pytest.fixture
def type_system() -> TypeSystem:
    ts = TypeSystem()
    ts.enable_generics = True
    return ts


@pytest.fixture
def cluster() -> ModuleTestCluster:
    c = ModuleTestCluster(linenos=-1)
    c.type_system.enable_generics = True
    return c


T = typing.TypeVar("T")
K = typing.TypeVar("K")
V = typing.TypeVar("V")


def _make_callable_data(accessible) -> CallableData:
    return CallableData(
        accessible=accessible,
        tree=None,
        description=None,
        cyclomatic_complexity=None,
    )


def test_collect_signature_type_vars_empty(type_system: TypeSystem):
    sig = InferredSignature(
        signature=inspect.Signature(),
        original_return_type=ANY,
        original_parameters={},
        type_system=type_system,
    )
    assert generics.collect_signature_type_vars(sig) == []


def test_collect_signature_type_vars_sorted(type_system: TypeSystem):
    tv_v = TypeVarType("V", raw_type_var=V)
    tv_k = TypeVarType("K", raw_type_var=K)
    py_sig = inspect.Signature(
        parameters=[
            inspect.Parameter("k", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        ]
    )
    sig = InferredSignature(
        signature=py_sig,
        original_return_type=tv_v,
        original_parameters={"k": tv_k},
        type_system=type_system,
    )
    result = generics.collect_signature_type_vars(sig)
    assert [tv.name for tv in result] == ["K", "V"]


def test_make_substitutions_basic(type_system: TypeSystem):
    int_type = type_system.to_type_info(int)
    assert int_type is not None
    int_inst = Instance(int_type)

    tv_t = TypeVarType("T", raw_type_var=T)
    subst = generics.make_substitutions([tv_t], [int_inst])

    assert subst[tv_t] == int_inst
    assert subst["T"] == int_inst
    assert subst[T] == int_inst


def test_make_substitutions_with_base_and_raw_typevar(type_system: TypeSystem):
    int_type = type_system.to_type_info(int)
    str_type = type_system.to_type_info(str)
    assert int_type is not None
    assert str_type is not None
    int_inst = Instance(int_type)
    str_inst = Instance(str_type)

    base = {"base_key": int_inst}
    subst = generics.make_substitutions([T], [str_inst], base_substitutions=base)

    assert subst["base_key"] == int_inst
    assert subst[T] == str_inst
    assert subst["T"] == str_inst


def test_generate_candidate_combinations(type_system: TypeSystem):
    tv_t = TypeVarType("T", raw_type_var=T)
    combos = generics.generate_candidate_combinations(type_system, [tv_t], max_combinations=2)
    assert len(combos) == 2
    for combo in combos:
        assert len(combo) == 1
        assert isinstance(combo[0], ProperType)


def test_instantiate_generic_function(cluster: ModuleTestCluster):
    def dummy_func(x):
        return x

    tv_t = TypeVarType("T", raw_type_var=T)
    sig = InferredSignature(
        signature=inspect.signature(dummy_func),
        original_return_type=tv_t,
        original_parameters={"x": tv_t},
        type_system=cluster.type_system,
    )
    dummy_gen_func = GenericFunction(dummy_func, sig, set(), "dummy_func")
    func_data = _make_callable_data(dummy_gen_func)

    generics.instantiate_generic_function(
        func_name="dummy_func",
        func=dummy_func,
        inferred_signature=sig,
        func_tvs=[tv_t],
        expected_exceptions=set(),
        function_data=func_data,
        test_cluster=cluster,
        add_to_test=True,
    )

    registered_funcs = [
        obj for obj in cluster.accessible_objects_under_test if isinstance(obj, GenericFunction)
    ]
    assert len(registered_funcs) > 0
    for fn in registered_funcs:
        assert not fn.inferred_signature.contains_type_vars()
        assert fn in cluster.all_accessible_objects


def test_instantiate_generic_function_with_ml_data(cluster: ModuleTestCluster):
    def dummy_func(x):
        return x

    tv_t = TypeVarType("T", raw_type_var=T)
    sig = InferredSignature(
        signature=inspect.signature(dummy_func),
        original_return_type=tv_t,
        original_parameters={"x": tv_t},
        type_system=cluster.type_system,
    )
    dummy_gen_func = GenericFunction(dummy_func, sig, set(), "dummy_func")
    func_data = _make_callable_data(dummy_gen_func)
    ml_data_mock = MagicMock()

    config.configuration.pynguinml.ml_testing_enabled = True
    try:
        generics.instantiate_generic_function(
            func_name="dummy_func",
            func=dummy_func,
            inferred_signature=sig,
            func_tvs=[tv_t],
            expected_exceptions=set(),
            function_data=func_data,
            test_cluster=cluster,
            add_to_test=False,
            ml_data=ml_data_mock,
        )
        for obj in cluster.all_accessible_objects:
            assert cluster.get_ml_data_for(obj) == ml_data_mock
    finally:
        config.configuration.pynguinml.ml_testing_enabled = False


def test_instantiate_generic_constructors(cluster: ModuleTestCluster):
    class Box:
        def __init__(self, value):
            self.value = value

    type_info = cluster.type_system.to_type_info(Box)
    assert type_info is not None
    tv_t = TypeVarType("T", raw_type_var=T)
    type_info.type_parameters = [tv_t]

    sig = InferredSignature(
        signature=inspect.signature(Box.__init__),
        original_return_type=NoneType(),
        original_parameters={"value": tv_t},
        type_system=cluster.type_system,
    )
    base_constructor = GenericConstructor(type_info, sig, set())
    constructor_data = _make_callable_data(base_constructor)

    inst_types = generics.instantiate_generic_constructors(
        type_info=type_info,
        generic_constructor=base_constructor,
        expected_exceptions=set(),
        constructor_data=constructor_data,
        test_cluster=cluster,
        add_to_test=True,
    )

    assert len(inst_types) > 0
    registered_ctors = [
        obj for obj in cluster.accessible_objects_under_test if isinstance(obj, GenericConstructor)
    ]
    assert len(registered_ctors) == len(inst_types)
    for ctor in registered_ctors:
        assert isinstance(ctor.generated_type(), Instance)
        assert not ctor.generated_type().contains_type_vars()


def test_instantiate_generic_constructors_not_generator(cluster: ModuleTestCluster):
    class Box:
        def __init__(self, value):
            self.value = value

    type_info = cluster.type_system.to_type_info(Box)
    assert type_info is not None
    tv_t = TypeVarType("T", raw_type_var=T)
    type_info.type_parameters = [tv_t]

    sig = InferredSignature(
        signature=inspect.signature(Box.__init__),
        original_return_type=NoneType(),
        original_parameters={"value": tv_t},
        type_system=cluster.type_system,
    )
    base_constructor = GenericConstructor(type_info, sig, set())
    constructor_data = _make_callable_data(base_constructor)

    generics.instantiate_generic_constructors(
        type_info=type_info,
        generic_constructor=base_constructor,
        expected_exceptions=set(),
        constructor_data=constructor_data,
        test_cluster=cluster,
        add_to_test=False,
        collections_or_primitives=[Box],
    )

    assert len(cluster.all_accessible_objects) == 0


def test_register_generic_or_normal_method_with_instantiated_types(
    cluster: ModuleTestCluster,
):
    class Box:
        def get_value(self):
            return 42

    type_info = cluster.type_system.to_type_info(Box)
    assert type_info is not None
    tv_t = TypeVarType("T", raw_type_var=T)
    type_info.type_parameters = [tv_t]

    int_type = cluster.type_system.to_type_info(int)
    assert int_type is not None
    inst_box = Instance(type_info, (Instance(int_type),))

    sig = InferredSignature(
        signature=inspect.signature(Box.get_value),
        original_return_type=tv_t,
        original_parameters={},
        type_system=cluster.type_system,
    )
    method = Box.get_value
    gen_method = GenericMethod(type_info, method, sig, set(), "get_value")
    m_data = _make_callable_data(gen_method)

    generics.register_generic_or_normal_method(
        type_info=type_info,
        method_name="get_value",
        method=method,
        generic_method=gen_method,
        method_data=m_data,
        inferred_signature=sig,
        expected_exceptions=set(),
        test_cluster=cluster,
        effective_add_to_test=True,
        instantiated_types=[inst_box],
    )

    # Generic method registered as generator and modifier
    assert gen_method in cluster.modifiers[type_info]
    # Instantiated method registered in accessible_objects_under_test
    inst_methods = [
        obj
        for obj in cluster.accessible_objects_under_test
        if isinstance(obj, GenericMethod) and obj.method_name == "get_value"
    ]
    assert len(inst_methods) == 1
    assert inst_methods[0].instantiated_owner == inst_box


def test_register_generic_or_normal_method_generic_signature_no_instantiated_types(
    cluster: ModuleTestCluster,
):
    class NonGenericClass:
        def generic_method(self, x):
            return x

    type_info = cluster.type_system.to_type_info(NonGenericClass)
    assert type_info is not None
    tv_t = TypeVarType("T", raw_type_var=T)
    sig = InferredSignature(
        signature=inspect.signature(NonGenericClass.generic_method),
        original_return_type=tv_t,
        original_parameters={"x": tv_t},
        type_system=cluster.type_system,
    )
    method = NonGenericClass.generic_method
    gen_method = GenericMethod(type_info, method, sig, set(), "generic_method")
    m_data = _make_callable_data(gen_method)

    generics.register_generic_or_normal_method(
        type_info=type_info,
        method_name="generic_method",
        method=method,
        generic_method=gen_method,
        method_data=m_data,
        inferred_signature=sig,
        expected_exceptions=set(),
        test_cluster=cluster,
        effective_add_to_test=True,
        instantiated_types=None,
    )

    inst_methods = [
        obj
        for obj in cluster.accessible_objects_under_test
        if isinstance(obj, GenericMethod) and obj.method_name == "generic_method"
    ]
    assert len(inst_methods) > 0
    for m in inst_methods:
        assert not m.inferred_signature.contains_type_vars()


def test_register_generic_or_normal_method_plain(cluster: ModuleTestCluster):
    class PlainClass:
        def normal_method(self):
            return 1

    type_info = cluster.type_system.to_type_info(PlainClass)
    assert type_info is not None
    sig = InferredSignature(
        signature=inspect.signature(PlainClass.normal_method),
        original_return_type=ANY,
        original_parameters={},
        type_system=cluster.type_system,
    )
    method = PlainClass.normal_method
    gen_method = GenericMethod(type_info, method, sig, set(), "normal_method")
    m_data = _make_callable_data(gen_method)

    generics.register_generic_or_normal_method(
        type_info=type_info,
        method_name="normal_method",
        method=method,
        generic_method=gen_method,
        method_data=m_data,
        inferred_signature=sig,
        expected_exceptions=set(),
        test_cluster=cluster,
        effective_add_to_test=True,
    )

    assert gen_method in cluster.accessible_objects_under_test
    assert gen_method in cluster.modifiers[type_info]
