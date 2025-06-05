#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import enum
import importlib
import inspect

from inspect import Parameter
from inspect import Signature
from unittest import mock
from unittest.mock import MagicMock
from unittest.mock import call

import pytest

import pynguin.configuration as config
import pynguin.testcase.statement as stmt
import pynguin.testcase.testfactory as tf
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.typetracing as tt

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import ModuleTestCluster
from pynguin.analyses.typesystem import AnyType
from pynguin.analyses.typesystem import InferredSignature
from pynguin.analyses.typesystem import NoneType
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.orderedset import OrderedSet
from tests.fixtures.examples.monkey import Monkey
from tests.testutils import feed_typesystem


def test_append_statement_unknown_type(test_case_mock):
    factory = tf.TestFactory(MagicMock(ModuleTestCluster))
    with pytest.raises(ConstructionFailedException):
        factory.append_statement(test_case_mock, MagicMock(Monkey))


@pytest.mark.parametrize(
    "method",
    [
        "add_constructor",
        "add_method",
        "add_function",
        "add_field",
    ],
)
def test_check_recursion_depth_guard(test_case_mock, method):
    with pytest.raises(ConstructionFailedException):
        getattr(tf.TestFactory(MagicMock(ModuleTestCluster)), method)(
            test_case_mock, MagicMock(stmt.Statement), recursion_depth=11
        )


@pytest.mark.parametrize(
    "statement",
    [
        (MagicMock(stmt.ConstructorStatement)),
        (MagicMock(stmt.MethodStatement)),
        (MagicMock(stmt.FunctionStatement, should_mutate=True)),
        (MagicMock(stmt.FieldStatement)),
        (MagicMock(stmt.PrimitiveStatement)),
    ],
)
def test_append_statement(test_case_mock, statement):
    called = False

    def mock_method(_t, _s, position=0, allow_none=True):  # noqa: ARG001, FBT002
        nonlocal called
        called = True

    factory = tf.TestFactory(MagicMock(ModuleTestCluster))
    factory.add_constructor = mock_method
    factory.add_method = mock_method
    factory.add_function = mock_method
    factory.add_field = mock_method
    factory.add_primitive = mock_method
    factory.append_statement(test_case_mock, statement)
    assert called


@pytest.mark.parametrize(
    "statement",
    [
        (MagicMock(gao.GenericConstructor)),
        (MagicMock(gao.GenericMethod)),
        (MagicMock(gao.GenericFunction)),
        (MagicMock(gao.GenericField)),
    ],
)
def test_append_generic_statement(test_case_mock, statement):
    called = False

    def mock_method(
        _t,
        _s,
        position=0,  # noqa: ARG001
        allow_none=True,  # noqa: ARG001, FBT002
        recursion_depth=11,  # noqa: ARG001
    ):
        nonlocal called
        called = True

    factory = tf.TestFactory(MagicMock(ModuleTestCluster))
    factory.add_constructor = mock_method
    factory.add_method = mock_method
    factory.add_function = mock_method
    factory.add_field = mock_method
    factory.add_primitive = mock_method
    result = factory.append_generic_accessible(test_case_mock, statement)
    assert result is None
    assert called


def test_append_illegal_generic_statement(test_case_mock):
    factory = tf.TestFactory(MagicMock(ModuleTestCluster))
    with pytest.raises(ConstructionFailedException):
        factory.append_generic_accessible(
            test_case_mock, MagicMock(stmt.PrimitiveStatement), position=42
        )


def test_add_primitive(test_case_mock):
    statement = MagicMock(stmt.PrimitiveStatement)
    statement.clone.return_value = statement
    factory = tf.TestFactory(MagicMock(ModuleTestCluster))
    factory.add_primitive(test_case_mock, statement)
    statement.clone.assert_called_once()
    test_case_mock.add_variable_creating_statement.assert_called_once()


def test_add_constructor(provide_callables_from_fixtures_modules, default_test_case):
    generic_constructor = gao.GenericConstructor(
        owner=default_test_case.test_cluster.type_system.to_type_info(
            provide_callables_from_fixtures_modules["Basket"]
        ),
        inferred_signature=InferredSignature(
            signature=Signature(
                parameters=[
                    Parameter(name="foo", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                ]
            ),
            original_return_type=default_test_case.test_cluster.type_system.convert_type_hint(None),
            original_parameters={
                "foo": default_test_case.test_cluster.type_system.convert_type_hint(int)
            },
            type_system=default_test_case.test_cluster.type_system,
        ),
    )
    factory = tf.TestFactory(default_test_case.test_cluster)
    result = factory.add_constructor(default_test_case, generic_constructor, position=0)
    assert result.type == default_test_case.test_cluster.type_system.convert_type_hint(
        provide_callables_from_fixtures_modules["Basket"]
    )
    assert default_test_case.size() == 2


def test_add_method(provide_callables_from_fixtures_modules, default_test_case):
    object_ = Monkey("foo")
    methods = inspect.getmembers(object_, inspect.ismethod)
    # fmt: off
    generic_method = gao.GenericMethod(
        owner=default_test_case.test_cluster.type_system.to_type_info(
            provide_callables_from_fixtures_modules["Monkey"]
        ),
        method=methods[3][1],
        inferred_signature=InferredSignature(
            signature=Signature(
                parameters=[
                    Parameter(
                        name="sentence",
                        kind=Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=str,
                    ),
                ]
            ),
            original_return_type=default_test_case.test_cluster.type_system
            .convert_type_hint(
                provide_callables_from_fixtures_modules["Monkey"]
            ),
            original_parameters={
                "sentence": default_test_case.test_cluster.type_system
                .convert_type_hint(str)
            },
            type_system=default_test_case.test_cluster.type_system,
        ),
    )
    # fmt: on
    factory = tf.TestFactory(default_test_case.test_cluster)
    config.configuration.test_creation.none_probability = 1.0
    result = factory.add_method(default_test_case, generic_method, position=0, callee=MagicMock())
    assert result.type == default_test_case.test_cluster.type_system.convert_type_hint(
        provide_callables_from_fixtures_modules["Monkey"]
    )
    assert default_test_case.size() == 2


def test_add_function(provide_callables_from_fixtures_modules, default_test_case):
    config.configuration.test_creation.object_reuse_probability = 0.0
    generic_function = gao.GenericFunction(
        function=default_test_case.test_cluster.type_system.to_type_info(
            provide_callables_from_fixtures_modules["triangle"]
        ),
        inferred_signature=InferredSignature(
            signature=Signature(
                parameters=[
                    Parameter(name="x", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                    Parameter(name="y", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                    Parameter(name="z", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int),
                ]
            ),
            original_return_type=default_test_case.test_cluster.type_system.convert_type_hint(None),
            original_parameters={
                "x": default_test_case.test_cluster.type_system.convert_type_hint(int),
                "y": default_test_case.test_cluster.type_system.convert_type_hint(int),
                "z": default_test_case.test_cluster.type_system.convert_type_hint(int),
            },
            type_system=default_test_case.test_cluster.type_system,
        ),
    )
    factory = tf.TestFactory(default_test_case.test_cluster)
    result = factory.add_function(default_test_case, generic_function, position=0)
    assert isinstance(result.type, AnyType)
    assert default_test_case.size() <= 4


def test_add_enum(default_test_case):
    enum_ = enum.Enum("Foo", "BAR")
    generic_enum = gao.GenericEnum(default_test_case.test_cluster.type_system.to_type_info(enum_))
    cluster = MagicMock(ModuleTestCluster)
    factory = tf.TestFactory(cluster)
    result = factory.add_enum(default_test_case, generic_enum)
    assert default_test_case.statements[0].value_name == "BAR"
    assert result.type == default_test_case.test_cluster.type_system.convert_type_hint(enum_)
    assert default_test_case.size() == 1


@pytest.mark.parametrize(
    "type_",
    [
        int,
        float,
        bool,
        str,
    ],
)
def test_create_primitive(type_, default_test_case):
    default_test_case.test_cluster.type_system.enable_numeric_tower()
    proper = default_test_case.test_cluster.type_system.convert_type_hint(type_)
    factory = tf.TestFactory(default_test_case.test_cluster)
    provider = EmptyConstantProvider()
    result = factory._create_primitive(
        default_test_case,
        proper,
        position=0,
        recursion_depth=0,
        constant_provider=provider,
    )[0]
    assert default_test_case.test_cluster.type_system.is_subtype(result.type, proper)


def test_attempt_generation_for_unknown_type(default_test_case):
    default_test_case.test_cluster.type_system.enable_numeric_tower()
    factory = tf.TestFactory(default_test_case.test_cluster)
    result = factory._attempt_generation(
        test_case=default_test_case,
        parameter_type=default_test_case.test_cluster.type_system.convert_type_hint(MagicMock),
        position=0,
        recursion_depth=0,
        allow_none=True,
    )
    assert result is None


def test_attempt_generation_for_none_type(default_test_case):
    factory = tf.TestFactory(default_test_case.test_cluster)
    result = factory._attempt_generation(
        test_case=default_test_case,
        parameter_type=NoneType(),
        position=0,
        recursion_depth=0,
        allow_none=True,
    )
    assert result.distance == 0


def test_attempt_generation_for_int_with_no_probability(default_test_case):
    config.configuration.test_creation.none_probability = 0.0
    factory = tf.TestFactory(default_test_case.test_cluster)
    result = factory._attempt_generation(
        test_case=default_test_case,
        parameter_type=default_test_case.test_cluster.type_system.convert_type_hint(MagicMock),
        position=0,
        recursion_depth=0,
        allow_none=True,
    )
    assert result is None


def test_attempt_generation_for_type_from_cluster(default_test_case):
    def mock_method(_, position, recursion_depth, allow_none, type_generators):
        assert position == 0  # pragma: no cover
        assert recursion_depth == 0  # pragma: no cover
        assert allow_none  # pragma: no cover
        assert isinstance(type_generators, gao.GenericAccessibleObject)  # pragma: no cover

    default_test_case.test_cluster.get_generators_for = lambda _: MagicMock(
        gao.GenericAccessibleObject
    )  # pragma: no cover
    factory = tf.TestFactory(default_test_case.test_cluster)
    factory._attempt_generation_for_type = mock_method
    factory._attempt_generation(
        test_case=default_test_case,
        parameter_type=NoneType(),
        position=0,
        recursion_depth=0,
        allow_none=True,
    )


def test__rollback_changes_mid(default_test_case):
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 10))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 15))

    cloned = default_test_case.clone()
    default_test_case.add_statement(stmt.FloatPrimitiveStatement(default_test_case, 7.5), 1)
    assert cloned != default_test_case

    tf.TestFactory._rollback_changes(default_test_case, cloned.size(), 1)
    assert cloned == default_test_case


def test__rollback_changes_end(default_test_case):
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 10))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 15))

    cloned = default_test_case.clone()
    default_test_case.add_statement(stmt.FloatPrimitiveStatement(default_test_case, 7.5), 3)
    assert cloned != default_test_case

    tf.TestFactory._rollback_changes(default_test_case, cloned.size(), 3)
    assert cloned == default_test_case


def test__rollback_changes_nothing_to_rollback(default_test_case):
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 10))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 15))

    cloned = default_test_case.clone()

    tf.TestFactory._rollback_changes(default_test_case, cloned.size(), 3)
    assert cloned == default_test_case


def test__dependencies_satisfied_no_dependencies():
    factory = tf.TestFactory(ModuleTestCluster(0))
    assert factory._dependencies_satisfied(OrderedSet(), [])


@pytest.mark.parametrize(
    "exist,req,result",
    [
        ([int, bool], [int, float], False),
        ([int, bool], [int, bool], True),
        ([], [], True),
        ([], [int], False),
    ],
)
def test__dependencies_satisfied(default_test_case, exist, req, result):
    factory = tf.TestFactory(ModuleTestCluster(0))
    objects = [
        vr.VariableReference(
            default_test_case,
            default_test_case.test_cluster.type_system.convert_type_hint(ex),
        )
        for ex in exist
    ]
    assert (
        factory._dependencies_satisfied(
            OrderedSet([
                default_test_case.test_cluster.type_system.convert_type_hint(re) for re in req
            ]),
            objects,
        )
        is result
    )


def test__get_possible_calls_no_calls(type_system):
    cluster = MagicMock(ModuleTestCluster)
    cluster.get_generators_for.return_value = OrderedSet(), False
    assert (
        tf.TestFactory(cluster)._get_possible_calls(type_system.convert_type_hint(int), [], {})
        == []
    )


def test__get_possible_calls_single_call(default_test_case, function_mock):
    cluster = default_test_case.test_cluster
    cluster.get_generators_for = lambda _: ({function_mock}, False)
    assert tf.TestFactory(cluster)._get_possible_calls(
        cluster.type_system.convert_type_hint(float),
        [vr.VariableReference(default_test_case, cluster.type_system.convert_type_hint(float))],
        {},
    ) == [function_mock]


def test__get_possible_calls_no_match(default_test_case, function_mock):
    cluster = default_test_case.test_cluster
    cluster.get_generators_for = lambda _: ({function_mock}, False)
    assert (
        tf.TestFactory(cluster)._get_possible_calls(
            cluster.type_system.convert_type_hint(float),
            [vr.VariableReference(default_test_case, cluster.type_system.convert_type_hint(int))],
            {},
        )
        == []
    )


@pytest.fixture
def sample_test_case(function_mock, default_test_case):
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_prim2 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_function1 = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_prim.ret_val}
    )
    float_function2 = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_function1.ret_val}
    )
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(float_prim2)
    default_test_case.add_statement(float_function1)
    default_test_case.add_statement(float_function2)
    return default_test_case


def test__get_reference_position_multi(sample_test_case):
    assert tf.TestFactory._get_reference_positions(sample_test_case, 0) == {
        0,
        2,
        3,
    }


def test__get_reference_position_single(sample_test_case):
    assert tf.TestFactory._get_reference_positions(sample_test_case, 3) == {3}


def test__recursive_delete_inclusion_multi(sample_test_case):
    to_delete = set()
    tf.TestFactory._recursive_delete_inclusion(sample_test_case, to_delete, 0)
    assert to_delete == {0, 2, 3}


def test__recursive_delete_inclusion_single(sample_test_case):
    to_delete = set()
    tf.TestFactory._recursive_delete_inclusion(sample_test_case, to_delete, 3)
    assert to_delete == {3}


def test_delete_statement_multi(sample_test_case):
    tf.TestFactory.delete_statement(sample_test_case, 0)
    assert sample_test_case.size() == 1


def test_delete_statement_single(sample_test_case):
    tf.TestFactory.delete_statement(sample_test_case, 3)
    assert sample_test_case.size() == 3


def test_delete_statement_reverse(test_case_mock):
    with mock.patch.object(tf.TestFactory, "_recursive_delete_inclusion") as rec_mock:
        rec_mock.side_effect = lambda _t, delete, _p: delete.update({1, 2, 3})
        tf.TestFactory.delete_statement(test_case_mock, 0)
        test_case_mock.remove.assert_has_calls([call(3), call(2), call(1)])


def test_get_reuse_parameters(default_test_case):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float1 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    default_test_case.add_statement(float0)
    default_test_case.add_statement(float1)
    sign_mock = MagicMock(inspect.Signature)
    params = {
        "test0": default_test_case.test_cluster.type_system.convert_type_hint(float),
        "test1": default_test_case.test_cluster.type_system.convert_type_hint(float),
    }
    inf_sig = InferredSignature(
        original_parameters=params,
        signature=sign_mock,
        type_system=default_test_case.test_cluster.type_system,
        original_return_type=default_test_case.test_cluster.type_system.convert_type_hint(None),
    )
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch("pynguin.testcase.testfactory.is_optional_parameter") as optional_mock:
            optional_mock.side_effect = [False, True]
            assert tf.TestFactory._get_reuse_parameters(default_test_case, inf_sig, 1, {}) == {
                "test0": float0.ret_val
            }


def test_insert_random_statement_empty_call(default_test_case):
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.return_value = True
            assert (
                test_factory.insert_random_statement(default_test_case, default_test_case.size())
                == 0
            )
            ins_mock.assert_called_with(default_test_case, 0)


def test_insert_random_statement_empty_on_object(default_test_case):
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 1.0
        with mock.patch.object(test_factory, "insert_random_call_on_object") as ins_mock:
            ins_mock.return_value = True
            assert (
                test_factory.insert_random_statement(default_test_case, default_test_case.size())
                == 0
            )
            ins_mock.assert_called_with(default_test_case, 0)


def test_insert_random_statement_non_empty(default_test_case):
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.return_value = True
            assert test_factory.insert_random_statement(
                default_test_case, default_test_case.size()
            ) in range(default_test_case.size() + 1)
            assert ins_mock.call_args_list[0].args[1] in range(default_test_case.size() + 1)


def test_insert_random_statement_non_empty_multi_insert(default_test_case):
    def side_effect(tc, pos):  # noqa: ARG001
        tc.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
        tc.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
        return True

    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.side_effect = side_effect
            assert test_factory.insert_random_statement(
                default_test_case, default_test_case.size()
            ) in range(1, 1 + default_test_case.size() + 1)
            assert ins_mock.call_args_list[0].args[1] in range(default_test_case.size() + 1)


def test_insert_random_statement_no_success(default_test_case):
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.return_value = False
            assert (
                test_factory.insert_random_statement(default_test_case, default_test_case.size())
                == -1
            )
            assert ins_mock.call_args_list[0].args[1] in range(default_test_case.size() + 1)


def test_insert_random_call_on_object_no_success(default_test_case):
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 0
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "_select_random_variable_for_call") as select_mock:
        select_mock.return_value = None
        assert not test_factory.insert_random_call_on_object(default_test_case, 0)
        select_mock.assert_called_with(default_test_case, 0)


def test_insert_random_call_on_object_success(variable_reference_mock, default_test_case):
    test_cluster = MagicMock(ModuleTestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "_select_random_variable_for_call") as select_mock:
        select_mock.return_value = variable_reference_mock
        with mock.patch.object(test_factory, "insert_random_call_on_object_at") as insert_mock:
            insert_mock.return_value = True
            assert test_factory.insert_random_call_on_object(default_test_case, 0)
            select_mock.assert_called_with(default_test_case, 0)
            insert_mock.assert_called_with(default_test_case, variable_reference_mock, 0)


def test_insert_random_call_on_object_retry(variable_reference_mock, default_test_case):
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "_select_random_variable_for_call") as select_mock:
        select_mock.return_value = variable_reference_mock
        with mock.patch.object(
            test_factory, "insert_random_call_on_object_at"
        ) as insert_random_at_mock:
            insert_random_at_mock.return_value = False
            with mock.patch.object(test_factory, "insert_random_call") as insert_random_mock:
                insert_random_mock.return_value = False
                assert not test_factory.insert_random_call_on_object(default_test_case, 0)
                select_mock.assert_called_with(default_test_case, 0)
                insert_random_at_mock.assert_called_with(
                    default_test_case, variable_reference_mock, 0
                )
                insert_random_mock.assert_called_with(default_test_case, 0)


def test_insert_random_call_on_object_at_no_accessible(test_case_mock, variable_reference_mock):
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.get_random_call_for.side_effect = ConstructionFailedException()
    test_factory = tf.TestFactory(test_cluster)
    variable_reference_mock.type = float
    assert not test_factory.insert_random_call_on_object_at(
        test_case_mock, variable_reference_mock, 0
    )


@pytest.mark.parametrize("result", [True, False])
def test_insert_random_call_on_object_at_success(test_case_mock, variable_reference_mock, result):
    test_cluster = MagicMock(ModuleTestCluster)
    test_factory = tf.TestFactory(test_cluster)
    variable_reference_mock.type = float
    with mock.patch.object(test_factory, "add_call_for") as call_mock:
        call_mock.return_value = result
        assert (
            test_factory.insert_random_call_on_object_at(test_case_mock, variable_reference_mock, 0)
            == result
        )


def test_add_call_for_field(field_mock, variable_reference_mock, test_case_mock):
    test_cluster = MagicMock(ModuleTestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "add_field") as add_field:
        assert test_factory.add_call_for(
            test_case_mock, variable_reference_mock, field_mock, position=0
        )
        add_field.assert_called_with(
            test_case_mock, field_mock, position=0, callee=variable_reference_mock
        )


def test_add_call_for_method(method_mock, variable_reference_mock, test_case_mock):
    test_cluster = MagicMock(ModuleTestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "add_method") as add_field:
        assert test_factory.add_call_for(
            test_case_mock, variable_reference_mock, method_mock, position=0
        )
        add_field.assert_called_with(
            test_case_mock, method_mock, position=0, callee=variable_reference_mock
        )


def test_add_call_for_rollback(method_mock, variable_reference_mock, default_test_case):
    def side_effect(tc, f, position, callee=None):  # noqa: ARG001
        tc.add_statement(stmt.IntPrimitiveStatement(tc, value=5), position=position)
        tc.add_statement(stmt.IntPrimitiveStatement(tc, value=5), position=position)
        tc.add_statement(stmt.IntPrimitiveStatement(tc, value=5), position=position)
        raise ConstructionFailedException

    int0 = stmt.IntPrimitiveStatement(default_test_case, 3)
    default_test_case.add_statement(int0)
    test_cluster = MagicMock(ModuleTestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "add_method") as add_field:
        add_field.side_effect = side_effect
        assert not test_factory.add_call_for(
            default_test_case, variable_reference_mock, method_mock, position=0
        )
        assert default_test_case.statements == [int0]


def test_add_call_for_unknown(variable_reference_mock, test_case_mock):
    test_cluster = MagicMock(ModuleTestCluster)
    test_factory = tf.TestFactory(test_cluster)
    unknown = MagicMock(gao.GenericAccessibleObject)
    unknown.is_method.return_value = False
    unknown.is_field.return_value = False
    with pytest.raises(RuntimeError):
        test_factory.add_call_for(test_case_mock, variable_reference_mock, unknown, 0)


def test_select_random_variable_for_call_one(constructor_mock, function_mock, default_test_case):
    default_test_case.add_statement(
        stmt.NoneStatement(
            default_test_case,
        )
    )
    default_test_case.add_statement(stmt.FloatPrimitiveStatement(default_test_case, 5.0))
    default_test_case.add_statement(stmt.FunctionStatement(default_test_case, function_mock))
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    default_test_case.add_statement(const)
    assert (
        tf.TestFactory._select_random_variable_for_call(default_test_case, default_test_case.size())
        == const.ret_val
    )


def test_select_random_variable_for_call_none(function_mock, default_test_case):
    default_test_case.add_statement(stmt.NoneStatement(default_test_case))
    default_test_case.add_statement(stmt.FloatPrimitiveStatement(default_test_case, 5.0))
    default_test_case.add_statement(stmt.FunctionStatement(default_test_case, function_mock))
    assert (
        tf.TestFactory._select_random_variable_for_call(default_test_case, default_test_case.size())
        is None
    )


def test_insert_random_call_no_accessible(test_case_mock):
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.get_random_accessible.return_value = None
    test_factory = tf.TestFactory(test_cluster)
    assert not test_factory.insert_random_call(test_case_mock, 0)


def test_insert_random_call_success(test_case_mock):
    test_cluster = MagicMock(ModuleTestCluster)
    acc = MagicMock(gao.GenericAccessibleObject)
    test_cluster.get_random_accessible.return_value = acc
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "append_generic_accessible") as append_mock:
        assert test_factory.insert_random_call(test_case_mock, position=0)
        append_mock.assert_called_with(test_case_mock, acc, position=0)


def test_insert_random_call_rollback(default_test_case):
    def side_effect(tc, f, position, callee=None):  # noqa: ARG001
        tc.add_statement(stmt.IntPrimitiveStatement(tc, 5), position=position)
        tc.add_statement(stmt.IntPrimitiveStatement(tc, 5), position=position)
        tc.add_statement(stmt.IntPrimitiveStatement(tc, 5), position=position)
        raise ConstructionFailedException

    int0 = stmt.IntPrimitiveStatement(default_test_case, 3)
    default_test_case.add_statement(int0)
    test_cluster = MagicMock(ModuleTestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "append_generic_accessible") as append_generic_mock:
        append_generic_mock.side_effect = side_effect
        assert not test_factory.insert_random_call(default_test_case, 0)
        assert default_test_case.statements == [int0]


def test_delete_statement_gracefully_success(function_mock, default_test_case):
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_prim2 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_function1 = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_prim2.ret_val}
    )
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(float_prim2)
    default_test_case.add_statement(float_function1)
    assert tf.TestFactory.delete_statement_gracefully(default_test_case, 1)
    assert default_test_case.statements[1].references(float_prim.ret_val)
    assert default_test_case.size() == 2


def test_delete_statement_gracefully_no_alternatives(function_mock, default_test_case):
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_function1 = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_prim.ret_val}
    )
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(float_function1)
    assert tf.TestFactory.delete_statement_gracefully(default_test_case, 0)
    assert default_test_case.size() == 0


def test_delete_statement_gracefully_no_dependencies(default_test_case):
    float_prim0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_prim1 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_prim2 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    default_test_case.add_statement(float_prim0)
    default_test_case.add_statement(float_prim1)
    default_test_case.add_statement(float_prim2)
    assert tf.TestFactory.delete_statement_gracefully(default_test_case, 1)
    assert default_test_case.statements == [float_prim0, float_prim2]


def test_delete_statement_gracefully_ml_statements(function_mock, default_test_case):
    config.configuration.pynguinml.ml_testing_enabled = True
    importlib.reload(tf)
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_prim2 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_ml_specific_function = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_prim2.ret_val}, should_mutate=False
    )
    float_function = stmt.FunctionStatement(
        default_test_case,
        function_mock,
        {"z": float_prim2.ret_val},
    )
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(float_prim2)
    default_test_case.add_statement(float_ml_specific_function)
    assert tf.MLTestFactory.delete_statement_gracefully(default_test_case, 1)
    assert default_test_case.size() == 1

    default_test_case.add_statement(float_prim2)
    default_test_case.add_statement(float_function)
    assert tf.MLTestFactory.delete_statement_gracefully(default_test_case, 1)
    assert default_test_case.size() == 2
    assert default_test_case.statements[1].references(float_prim.ret_val)


def test_change_random_call_unknown_type(default_test_case):
    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.get_generators_for.return_value = [], False
    test_factory = tf.TestFactory(test_cluster)
    none_statement = stmt.NoneStatement(default_test_case)
    default_test_case.add_statement(none_statement)
    assert not test_factory.change_random_call(default_test_case, none_statement)


def test_change_random_call_no_calls(function_mock, default_test_case):
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float_function1 = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_prim.ret_val}
    )
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(float_function1)

    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.get_generators_for.return_value = ({function_mock}, False)
    test_factory = tf.TestFactory(test_cluster)
    assert not test_factory.change_random_call(default_test_case, float_function1)


def test_change_random_call_primitive(function_mock, default_test_case):
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    default_test_case.add_statement(float_prim)

    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.get_generators_for.return_value = ({function_mock}, False)
    test_factory = tf.TestFactory(test_cluster)
    assert not test_factory.change_random_call(default_test_case, float_prim)


def test_change_random_call_success(
    function_mock, method_mock, constructor_mock, default_test_case
):
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    int0 = stmt.IntPrimitiveStatement(default_test_case, 2)
    float_function1 = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_prim.ret_val}
    )
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(int0)
    default_test_case.add_statement(const)
    default_test_case.add_statement(float_function1)

    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.get_generators_for.return_value = ({function_mock, method_mock}, False)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "change_call") as change_mock:
        assert test_factory.change_random_call(default_test_case, float_function1)
        # fmt: off
        change_mock.assert_called_with(
            default_test_case,
            float_function1,
            method_mock,
            {
                function_mock.inferred_signature: function_mock.inferred_signature
                .get_parameter_types(
                    {}
                ),
                method_mock.inferred_signature: method_mock.inferred_signature
                .get_parameter_types(
                    {}
                ),
            },
        )
        # fmt: on


def test_change_random_call_failed(function_mock, method_mock, constructor_mock, default_test_case):
    float_prim = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    int0 = stmt.IntPrimitiveStatement(default_test_case, 2)
    float_function1 = stmt.FunctionStatement(
        default_test_case, function_mock, {"z": float_prim.ret_val}
    )
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    default_test_case.add_statement(float_prim)
    default_test_case.add_statement(int0)
    default_test_case.add_statement(const)
    default_test_case.add_statement(float_function1)

    test_cluster = MagicMock(ModuleTestCluster)
    test_cluster.get_generators_for.return_value = ({function_mock, method_mock}, False)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "change_call") as change_mock:
        change_mock.side_effect = ConstructionFailedException()
        assert not test_factory.change_random_call(default_test_case, float_function1)
        # fmt: off
        change_mock.assert_called_with(
            default_test_case,
            float_function1,
            method_mock,
            {
                function_mock.inferred_signature: function_mock.inferred_signature
                .get_parameter_types(
                    {}
                ),
                method_mock.inferred_signature: method_mock.inferred_signature
                .get_parameter_types(
                    {}
                ),
            },
        )
        # fmt: on


def test_change_call_method(constructor_mock, method_mock, default_test_case):
    default_test_case.add_statement(stmt.ConstructorStatement(default_test_case, constructor_mock))
    default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 3))
    to_replace = stmt.NoneStatement(default_test_case)
    default_test_case.add_statement(to_replace)
    test_cluster = default_test_case.test_cluster
    feed_typesystem(test_cluster.type_system, constructor_mock)
    feed_typesystem(test_cluster.type_system, method_mock)
    test_factory = tf.TestFactory(test_cluster)
    test_factory.change_call(default_test_case, to_replace, method_mock, {})
    assert default_test_case.statements[2].accessible_object() == method_mock
    assert default_test_case.statements[2].ret_val is to_replace.ret_val


def test_change_call_constructor(constructor_mock, default_test_case):
    default_test_case.add_statement(stmt.FloatPrimitiveStatement(default_test_case, 3.5))
    to_replace = stmt.NoneStatement(default_test_case)
    default_test_case.add_statement(to_replace)
    test_cluster = default_test_case.test_cluster
    feed_typesystem(test_cluster.type_system, constructor_mock)
    test_factory = tf.TestFactory(test_cluster)
    test_factory.change_call(default_test_case, to_replace, constructor_mock, {})
    assert default_test_case.statements[1].accessible_object() == constructor_mock
    assert default_test_case.statements[1].ret_val is to_replace.ret_val


def test_change_call_function(function_mock, default_test_case):
    default_test_case.add_statement(stmt.FloatPrimitiveStatement(default_test_case, 3.5))
    to_replace = stmt.NoneStatement(default_test_case)
    default_test_case.add_statement(to_replace)
    test_cluster = default_test_case.test_cluster
    feed_typesystem(test_cluster.type_system, function_mock)
    test_factory = tf.TestFactory(test_cluster)
    test_factory.change_call(default_test_case, to_replace, function_mock, {})
    assert default_test_case.statements[1].accessible_object() == function_mock
    assert default_test_case.statements[1].ret_val is to_replace.ret_val


def test_change_call_unknown(default_test_case):
    default_test_case.add_statement(stmt.FloatPrimitiveStatement(default_test_case, 3.5))
    to_replace = stmt.NoneStatement(default_test_case)
    default_test_case.add_statement(to_replace)
    test_cluster = default_test_case.test_cluster
    test_factory = tf.TestFactory(test_cluster)
    acc = MagicMock(gao.GenericAccessibleObject)
    acc.is_method.return_value = False
    acc.is_constructor.return_value = False
    acc.is_function.return_value = False
    acc.is_enum.return_value = False
    with pytest.raises(AssertionError):
        test_factory.change_call(default_test_case, to_replace, acc, {})


def test_add_method_type_tracing_union_type(default_test_case):
    generic_method = gao.GenericMethod(
        owner=MagicMock(),
        method=MagicMock(),
        inferred_signature=InferredSignature(
            signature=Signature(
                parameters=[
                    Parameter(
                        name="sentence",
                        kind=Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=float | int,
                    ),
                ]
            ),
            original_return_type=MagicMock(),
            original_parameters={
                "sentence": default_test_case.test_cluster.type_system.convert_type_hint(str)
            },
            type_system=default_test_case.test_cluster.type_system,
        ),
    )

    usage_trace = MagicMock(tt.UsageTraceNode)
    usage_trace.__len__.return_value = 1
    usage_trace.children = {}
    ordered_set = OrderedSet()
    ordered_set.add(float | int)
    usage_trace.type_checks = ordered_set
    generic_method.inferred_signature.usage_trace["sentence"] = usage_trace
    factory = tf.TestFactory(default_test_case.test_cluster)
    factory.add_method(default_test_case, generic_method, position=0, callee=MagicMock())
