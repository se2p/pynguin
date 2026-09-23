# This file is part of the Pynguin automated unit test generation framework.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
"""Concrete type instantiation for generic classes, methods, and functions.

Derives concrete instantiations of generic types (Issue #64) and registers
the resulting constructors, methods, and functions into the ModuleTestCluster.
"""

from __future__ import annotations

import dataclasses
import enum
import itertools
import types
from typing import TYPE_CHECKING, Any

import pynguin.analyses.module as module_analysis
import pynguin.configuration as config
from pynguin.analyses.typesystem import (
    InferredSignature,
    Instance,
    ProperType,
    TypeInfo,
    TypeSystem,
    TypeVarType,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.orderedset import OrderedSet

if TYPE_CHECKING:
    import typing
    from collections.abc import Mapping, Sequence

    from pynguin.analyses.module import CallableData, ModuleTestCluster
    from pynguin.utils.pynguinml.ml_types import MLCallableData


def collect_signature_type_vars(signature: InferredSignature) -> list[TypeVarType]:
    """Collect all unique TypeVarTypes in an inferred signature, sorted deterministically.

    Args:
        signature: The inferred signature to inspect.

    Returns:
        List of unique TypeVarTypes found in the signature.
    """
    return sorted(signature.get_type_vars(), key=lambda tv: tv.name)


def make_substitutions(
    type_vars: Sequence[TypeVarType | typing.TypeVar],
    chosen_types: Sequence[ProperType],
    base_substitutions: Mapping[str | typing.TypeVar | TypeVarType, ProperType] | None = None,
) -> dict[str | typing.TypeVar | TypeVarType, ProperType]:
    """Build a substitution mapping from type variables to candidate types.

    Args:
        type_vars: The type variables to substitute.
        chosen_types: The concrete types chosen for each type variable.
        base_substitutions: Any existing substitutions to carry over.

    Returns:
        A dictionary mapping type variable objects, names, and raw TypeVars to concrete types.
    """
    substitutions: dict[str | typing.TypeVar | TypeVarType, ProperType] = (
        dict(base_substitutions) if base_substitutions else {}
    )
    for tv, candidate in zip(type_vars, chosen_types, strict=True):
        substitutions[tv] = candidate
        tv_name = tv.name if isinstance(tv, TypeVarType) else tv.__name__
        substitutions[tv_name] = candidate
        if isinstance(tv, TypeVarType) and tv.raw_type_var is not None:
            substitutions[tv.raw_type_var] = candidate
    return substitutions


def generate_candidate_combinations(
    type_system: TypeSystem,
    type_vars: Sequence[TypeVarType | typing.TypeVar],
    max_combinations: int = 10,
) -> list[tuple[ProperType, ...]]:
    """Generate up to max_combinations concrete type combinations for the given type variables.

    Args:
        type_system: The active type system to retrieve candidate types from.
        type_vars: Sequence of type variables to instantiate.
        max_combinations: Maximum number of combinations to generate.

    Returns:
        A list of concrete type tuples.
    """
    candidates = [type_system.get_candidate_types_for_type_var(tv) for tv in type_vars]
    return list(itertools.islice(itertools.product(*candidates), max_combinations))


def _register_accessible(
    *,
    test_cluster: ModuleTestCluster,
    accessible: GenericAccessibleObject,
    callable_data: CallableData,
    is_generator: bool = True,
    modifier_owner: TypeInfo | None = None,
    add_to_test: bool = False,
    ml_data: MLCallableData | None = None,
) -> None:
    """Register an accessible object into the test cluster."""
    if ml_data is not None and config.configuration.pynguinml.ml_testing_enabled:
        test_cluster.add_ml_data(accessible, ml_data)
    if is_generator:
        test_cluster.add_generator(accessible)
    if modifier_owner is not None:
        test_cluster.add_modifier(modifier_owner, accessible)
    if add_to_test:
        test_cluster.add_accessible_object_under_test(accessible, callable_data)


def instantiate_generic_function(
    *,
    func_name: str,
    func: types.FunctionType,
    inferred_signature: InferredSignature,
    func_tvs: Sequence[TypeVarType],
    expected_exceptions: set[str],
    function_data: CallableData,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
    ml_data: MLCallableData | None = None,
) -> None:
    """Instantiate and register generic variants of a function.

    Args:
        func_name: Function name.
        func: Python function object.
        inferred_signature: Inferred signature containing TypeVars.
        func_tvs: Sequence of TypeVars to instantiate.
        expected_exceptions: Set of expected exception names.
        function_data: Base CallableData for the function.
        test_cluster: Target test cluster.
        add_to_test: Whether to add as an accessible object under test.
        ml_data: Optional ML callable metadata.
    """
    combos = generate_candidate_combinations(
        test_cluster.type_system, func_tvs, max_combinations=10
    )
    for combo in combos:
        substitutions = make_substitutions(func_tvs, combo)
        subst_sig = inferred_signature.substitute(substitutions)
        inst_func = GenericFunction(func, subst_sig, expected_exceptions, func_name)
        inst_data = dataclasses.replace(function_data, accessible=inst_func)

        _register_accessible(
            test_cluster=test_cluster,
            accessible=inst_func,
            callable_data=inst_data,
            is_generator=True,
            add_to_test=add_to_test,
            ml_data=ml_data,
        )


def instantiate_generic_constructors(
    *,
    type_info: TypeInfo,
    generic_constructor: GenericConstructor,
    expected_exceptions: set[str],
    constructor_data: CallableData,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
    ml_data: MLCallableData | None = None,
    collections_or_primitives: Sequence[type] = (),
) -> list[Instance]:
    """Instantiate and register concrete constructor variants for a generic class.

    Args:
        type_info: The owner TypeInfo of the generic class.
        generic_constructor: The base generic constructor.
        expected_exceptions: Set of expected exception type names.
        constructor_data: Base CallableData for the constructor.
        test_cluster: Target test cluster.
        add_to_test: Whether to add as an accessible object under test.
        ml_data: Optional ML metadata.
        collections_or_primitives: Types that should not be registered as generators.

    Returns:
        List of created concrete Instance objects.
    """
    instantiated_types: list[Instance] = []
    combos = generate_candidate_combinations(
        test_cluster.type_system, type_info.type_parameters, max_combinations=10
    )
    is_gen = not (type_info.is_abstract or type_info.raw_type in collections_or_primitives)

    for combo in combos:
        concrete_instance = Instance(type_info, combo)
        instantiated_types.append(concrete_instance)

        substitutions = make_substitutions(type_info.type_parameters, combo)
        subst_sig = generic_constructor.inferred_signature.substitute(substitutions)
        subst_sig.return_type = concrete_instance

        inst_constructor = GenericConstructor(
            type_info,
            subst_sig,
            expected_exceptions,
            generated_type=concrete_instance,
        )
        inst_data = dataclasses.replace(constructor_data, accessible=inst_constructor)

        _register_accessible(
            test_cluster=test_cluster,
            accessible=inst_constructor,
            callable_data=inst_data,
            is_generator=is_gen,
            add_to_test=add_to_test,
            ml_data=ml_data,
        )

    return instantiated_types


def register_generic_or_normal_method(
    *,
    type_info: TypeInfo,
    method_name: str,
    method: Any,
    generic_method: GenericMethod,
    method_data: CallableData,
    inferred_signature: InferredSignature,
    expected_exceptions: set[str],
    test_cluster: ModuleTestCluster,
    effective_add_to_test: bool,
    instantiated_types: Sequence[Instance] | None = None,
    ml_data: MLCallableData | None = None,
) -> None:
    """Register method variants, instantiating generic types if applicable.

    Args:
        type_info: Owner TypeInfo.
        method_name: Method name string.
        method: Method callable.
        generic_method: Base uninstantiated GenericMethod.
        method_data: Base CallableData.
        inferred_signature: Inferred signature of the method.
        expected_exceptions: Set of expected exception names.
        test_cluster: Target ModuleTestCluster.
        effective_add_to_test: Whether method is an accessible object under test.
        instantiated_types: Concrete Instances of the owner class, if any.
        ml_data: Optional ML metadata.
    """
    is_generic = False

    if instantiated_types:
        is_generic = True
        for inst_type in instantiated_types:
            base_subst = make_substitutions(type_info.type_parameters, inst_type.args)
            _instantiate_method_with_owner(
                type_info=type_info,
                method=method,
                method_name=method_name,
                signature=inferred_signature,
                base_substitutions=base_subst,
                expected_exceptions=expected_exceptions,
                method_data=method_data,
                test_cluster=test_cluster,
                add_to_test=effective_add_to_test,
                instantiated_owner=inst_type,
                ml_data=ml_data,
            )
    elif collect_signature_type_vars(inferred_signature):
        is_generic = True
        _instantiate_method_with_owner(
            type_info=type_info,
            method=method,
            method_name=method_name,
            signature=inferred_signature,
            base_substitutions={},
            expected_exceptions=expected_exceptions,
            method_data=method_data,
            test_cluster=test_cluster,
            add_to_test=effective_add_to_test,
            instantiated_owner=None,
            ml_data=ml_data,
        )

    if is_generic:
        test_cluster.add_generator(generic_method)
        test_cluster.add_modifier(type_info, generic_method)
    else:
        _register_accessible(
            test_cluster=test_cluster,
            accessible=generic_method,
            callable_data=method_data,
            is_generator=True,
            modifier_owner=type_info,
            add_to_test=effective_add_to_test,
        )


def _instantiate_method_with_owner(
    *,
    type_info: TypeInfo,
    method: Any,
    method_name: str,
    signature: InferredSignature,
    base_substitutions: Mapping[str | typing.TypeVar | TypeVarType, ProperType],
    expected_exceptions: set[str],
    method_data: CallableData,
    test_cluster: ModuleTestCluster,
    add_to_test: bool,
    instantiated_owner: Instance | None,
    ml_data: MLCallableData | None,
) -> None:
    """Instantiate a method with a specific owner instance and substitute remaining TypeVars.

    Args:
        type_info: Owner TypeInfo.
        method: Method callable.
        method_name: Method name string.
        signature: Method inferred signature.
        base_substitutions: Initial substitutions from the owner instance.
        expected_exceptions: Set of expected exception names.
        method_data: Base CallableData.
        test_cluster: Target ModuleTestCluster.
        add_to_test: Whether method is an accessible object under test.
        instantiated_owner: Concrete Instance of the owner, or None.
        ml_data: Optional ML metadata.
    """
    inst_sig = signature.substitute(base_substitutions)
    rem_tvs = collect_signature_type_vars(inst_sig)
    combos = generate_candidate_combinations(test_cluster.type_system, rem_tvs, max_combinations=10)
    for combo in combos:
        m_subst = make_substitutions(rem_tvs, combo, base_substitutions)
        final_sig = signature.substitute(m_subst)
        inst_m = GenericMethod(
            type_info,
            method,
            final_sig,
            expected_exceptions,
            method_name,
            instantiated_owner=instantiated_owner,
        )
        inst_data = dataclasses.replace(method_data, accessible=inst_m)
        _register_accessible(
            test_cluster=test_cluster,
            accessible=inst_m,
            callable_data=inst_data,
            is_generator=True,
            modifier_owner=type_info,
            add_to_test=add_to_test,
            ml_data=ml_data,
        )


def _remove_accessible_under_test(
    test_cluster: ModuleTestCluster, obj: GenericAccessibleObject
) -> None:
    test_cluster.accessible_objects_under_test.discard(obj)
    test_cluster.function_data_for_accessibles.pop(obj, None)


def _instantiate_single_generic_function(
    test_cluster: ModuleTestCluster, gen_func: GenericFunction
) -> None:
    func_tvs = collect_signature_type_vars(gen_func.inferred_signature)
    if not func_tvs:
        return

    is_under_test = gen_func in test_cluster.accessible_objects_under_test
    func_data = test_cluster.function_data_for_accessibles.get(gen_func)
    if func_data is None:
        func_data = module_analysis.CallableData(
            accessible=gen_func,
            tree=None,
            description=None,
            cyclomatic_complexity=None,
        )
    ml_data = test_cluster.get_ml_data_for(gen_func)

    func_obj = gen_func.callable
    if not isinstance(func_obj, types.FunctionType):
        return
    func_name = str(gen_func.function_name or getattr(func_obj, "__name__", ""))
    instantiate_generic_function(
        func_name=func_name,
        func=func_obj,
        inferred_signature=gen_func.inferred_signature,
        func_tvs=func_tvs,
        expected_exceptions=gen_func.expected_exceptions,
        function_data=func_data,
        test_cluster=test_cluster,
        add_to_test=is_under_test,
        ml_data=ml_data,
    )
    if is_under_test:
        _remove_accessible_under_test(test_cluster, gen_func)


def _instantiate_generic_functions_in_cluster(test_cluster: ModuleTestCluster) -> None:
    candidate_funcs: OrderedSet[GenericFunction] = OrderedSet()
    for gens in test_cluster.generators.values():
        for gen in gens:
            if isinstance(gen, GenericFunction):
                candidate_funcs.add(gen)
    for obj in test_cluster.accessible_objects_under_test:
        if isinstance(obj, GenericFunction):
            candidate_funcs.add(obj)

    for gen_func in candidate_funcs:
        _instantiate_single_generic_function(test_cluster, gen_func)


def _find_constructor_for_type(
    test_cluster: ModuleTestCluster, type_info: TypeInfo
) -> GenericConstructor | None:
    inst_type = Instance(type_info)
    for g in test_cluster.generators.get(inst_type, ()):
        if isinstance(g, GenericConstructor) and g.owner == type_info:
            return g
    for obj in test_cluster.accessible_objects_under_test:
        if isinstance(obj, GenericConstructor) and obj.owner == type_info:
            return obj
    return None


def _instantiate_methods_for_owner(
    test_cluster: ModuleTestCluster,
    type_info: TypeInfo,
    instantiated_types: Sequence[Instance],
) -> None:
    modifiers = [
        m for m in list(test_cluster.modifiers.get(type_info, ())) if isinstance(m, GenericMethod)
    ]
    for m in modifiers:
        m_under_test = m in test_cluster.accessible_objects_under_test
        m_data = test_cluster.function_data_for_accessibles.get(m)
        if m_data is None:
            m_data = module_analysis.CallableData(
                accessible=m,
                tree=None,
                description=None,
                cyclomatic_complexity=None,
            )
        m_ml_data = test_cluster.get_ml_data_for(m)
        m_name = m.method_name or getattr(m.callable, "__name__", "")
        for inst_owner in instantiated_types:
            base_subst = make_substitutions(type_info.type_parameters, inst_owner.args)
            _instantiate_method_with_owner(
                type_info=type_info,
                method=m.callable,
                method_name=m_name,
                signature=m.inferred_signature,
                base_substitutions=base_subst,
                expected_exceptions=m.expected_exceptions,
                method_data=m_data,
                test_cluster=test_cluster,
                add_to_test=m_under_test,
                instantiated_owner=inst_owner,
                ml_data=m_ml_data,
            )
        if m_under_test:
            _remove_accessible_under_test(test_cluster, m)


def _instantiate_generic_class(test_cluster: ModuleTestCluster, type_info: TypeInfo) -> None:
    base_constructor = _find_constructor_for_type(test_cluster, type_info)
    if base_constructor is None:
        return

    is_under_test = base_constructor in test_cluster.accessible_objects_under_test
    ctor_data = test_cluster.function_data_for_accessibles.get(base_constructor)
    if ctor_data is None:
        ctor_data = module_analysis.CallableData(
            accessible=base_constructor,
            tree=None,
            description=None,
            cyclomatic_complexity=None,
        )
    ml_data = test_cluster.get_ml_data_for(base_constructor)

    instantiated_types = instantiate_generic_constructors(
        type_info=type_info,
        generic_constructor=base_constructor,
        expected_exceptions=base_constructor.expected_exceptions,
        constructor_data=ctor_data,
        test_cluster=test_cluster,
        add_to_test=is_under_test,
        ml_data=ml_data,
        collections_or_primitives=(*module_analysis.COLLECTIONS, *module_analysis.PRIMITIVES),
    )
    if is_under_test:
        _remove_accessible_under_test(test_cluster, base_constructor)

    _instantiate_methods_for_owner(test_cluster, type_info, instantiated_types)


def _instantiate_methods_in_non_generic_classes(
    test_cluster: ModuleTestCluster, type_info: TypeInfo
) -> None:
    modifiers = [
        m
        for m in list(test_cluster.modifiers.get(type_info, ()))
        if isinstance(m, GenericMethod) and collect_signature_type_vars(m.inferred_signature)
    ]
    for m in modifiers:
        m_under_test = m in test_cluster.accessible_objects_under_test
        m_data = test_cluster.function_data_for_accessibles.get(m)
        if m_data is None:
            m_data = module_analysis.CallableData(
                accessible=m,
                tree=None,
                description=None,
                cyclomatic_complexity=None,
            )
        m_ml_data = test_cluster.get_ml_data_for(m)
        m_name = m.method_name or getattr(m.callable, "__name__", "")
        _instantiate_method_with_owner(
            type_info=type_info,
            method=m.callable,
            method_name=m_name,
            signature=m.inferred_signature,
            base_substitutions={},
            expected_exceptions=m.expected_exceptions,
            method_data=m_data,
            test_cluster=test_cluster,
            add_to_test=m_under_test,
            instantiated_owner=None,
            ml_data=m_ml_data,
        )
        if m_under_test:
            _remove_accessible_under_test(test_cluster, m)


def _instantiate_generic_classes_and_methods_in_cluster(
    test_cluster: ModuleTestCluster,
) -> None:
    for type_info in list(test_cluster.type_system.get_all_types()):
        if type_info.is_generic and not (
            isinstance(type_info.raw_type, type) and issubclass(type_info.raw_type, enum.Enum)
        ):
            _instantiate_generic_class(test_cluster, type_info)
        elif not type_info.is_generic:
            _instantiate_methods_in_non_generic_classes(test_cluster, type_info)


def instantiate_generics_in_cluster(test_cluster: ModuleTestCluster) -> None:
    """Instantiate generic functions, classes, and methods in the test cluster.

    Args:
        test_cluster: The module test cluster to process.
    """
    _instantiate_generic_functions_in_cluster(test_cluster)
    _instantiate_generic_classes_and_methods_in_cluster(test_cluster)
