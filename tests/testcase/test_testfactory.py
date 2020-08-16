#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import inspect
from inspect import Parameter, Signature
from unittest import mock
from unittest.mock import MagicMock, call

import pytest

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.fieldstatement as f_stmt
import pynguin.testcase.statements.parametrizedstatements as par_stmt
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testfactory as tf
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.setup.testcluster import TestCluster
from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.exceptions import ConstructionFailedException
from tests.fixtures.examples.monkey import Monkey


@pytest.fixture()
def test_cluster_mock():
    cluster = MagicMock(TestCluster)
    cluster.get_generators_for.return_value = set()
    return cluster


def test_append_statement_unknown_type(test_case_mock):
    with pytest.raises(ConstructionFailedException):
        factory = tf.TestFactory(MagicMock(TestCluster))
        factory.append_statement(test_case_mock, MagicMock(Monkey))


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("add_constructor"),
        pytest.param("add_method"),
        pytest.param("add_function"),
        pytest.param("add_field"),
    ],
)
def test_check_recursion_depth_guard(test_case_mock, method):
    with pytest.raises(ConstructionFailedException):
        getattr(tf.TestFactory(MagicMock(TestCluster)), method)(
            test_case_mock, MagicMock(stmt.Statement), recursion_depth=11
        )


@pytest.mark.parametrize(
    "statement",
    [
        pytest.param(MagicMock(par_stmt.ConstructorStatement)),
        pytest.param(MagicMock(par_stmt.MethodStatement)),
        pytest.param(MagicMock(par_stmt.FunctionStatement)),
        pytest.param(MagicMock(f_stmt.FieldStatement)),
        pytest.param(MagicMock(prim.PrimitiveStatement)),
    ],
)
def test_append_statement(test_case_mock, statement):
    called = False

    def mock_method(t, s, position=0, allow_none=True):
        nonlocal called
        called = True

    factory = tf.TestFactory(MagicMock(TestCluster))
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
        pytest.param(MagicMock(gao.GenericConstructor)),
        pytest.param(MagicMock(gao.GenericMethod)),
        pytest.param(MagicMock(gao.GenericFunction)),
        pytest.param(MagicMock(gao.GenericField)),
    ],
)
def test_append_generic_statement(test_case_mock, statement):
    called = False

    def mock_method(t, s, position=0, allow_none=True, recursion_depth=11):
        nonlocal called
        called = True
        return None

    factory = tf.TestFactory(MagicMock(TestCluster))
    factory.add_constructor = mock_method
    factory.add_method = mock_method
    factory.add_function = mock_method
    factory.add_field = mock_method
    factory.add_primitive = mock_method
    result = factory.append_generic_statement(test_case_mock, statement)
    assert result is None
    assert called


def test_append_illegal_generic_statement(test_case_mock):
    factory = tf.TestFactory(MagicMock(TestCluster))
    with pytest.raises(ConstructionFailedException):
        factory.append_generic_statement(
            test_case_mock, MagicMock(prim.PrimitiveStatement), position=42
        )


def test_add_primitive(test_case_mock):
    statement = MagicMock(prim.PrimitiveStatement)
    statement.clone.return_value = statement
    factory = tf.TestFactory(MagicMock(TestCluster))
    factory.add_primitive(test_case_mock, statement)
    statement.clone.assert_called_once()
    test_case_mock.add_statement.assert_called_once()


def test_add_constructor(provide_callables_from_fixtures_modules):
    test_case = dtc.DefaultTestCase()
    generic_constructor = gao.GenericConstructor(
        owner=provide_callables_from_fixtures_modules["Basket"],
        inferred_signature=InferredSignature(
            signature=Signature(
                parameters=[
                    Parameter(
                        name="foo", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int
                    ),
                ]
            ),
            return_type=None,
            parameters={"foo": int},
        ),
    )
    cluster = MagicMock(TestCluster)
    cluster.select_concrete_type.side_effect = lambda x: x
    factory = tf.TestFactory(cluster)
    result = factory.add_constructor(test_case, generic_constructor, position=0)
    assert result.variable_type == provide_callables_from_fixtures_modules["Basket"]
    assert test_case.size() == 2


def test_add_method(provide_callables_from_fixtures_modules, test_cluster_mock):
    test_case = dtc.DefaultTestCase()
    object_ = Monkey("foo")
    methods = inspect.getmembers(object_, inspect.ismethod)
    generic_method = gao.GenericMethod(
        owner=provide_callables_from_fixtures_modules["Monkey"],
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
            return_type=provide_callables_from_fixtures_modules["Monkey"],
            parameters={"sentence": str},
        ),
    )
    test_cluster_mock.select_concrete_type.side_effect = lambda x: x
    factory = tf.TestFactory(test_cluster_mock)
    config.INSTANCE.none_probability = 1.0
    result = factory.add_method(test_case, generic_method, position=0)
    assert result.variable_type == provide_callables_from_fixtures_modules["Monkey"]
    assert test_case.size() == 3


def test_add_function(provide_callables_from_fixtures_modules):
    config.INSTANCE.object_reuse_probability = 0.0
    test_case = dtc.DefaultTestCase()
    generic_function = gao.GenericFunction(
        function=provide_callables_from_fixtures_modules["triangle"],
        inferred_signature=InferredSignature(
            signature=Signature(
                parameters=[
                    Parameter(
                        name="x", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int
                    ),
                    Parameter(
                        name="y", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int
                    ),
                    Parameter(
                        name="z", kind=Parameter.POSITIONAL_OR_KEYWORD, annotation=int
                    ),
                ]
            ),
            return_type=None,
            parameters={"x": int, "y": int, "z": int},
        ),
    )
    cluster = MagicMock(TestCluster)
    cluster.select_concrete_type.side_effect = lambda x: x
    factory = tf.TestFactory(cluster)
    result = factory.add_function(test_case, generic_function, position=0)
    assert isinstance(result.variable_type, type(None))
    assert test_case.size() <= 4


@pytest.mark.parametrize(
    "type_, statement_type",
    [
        pytest.param(int, int),
        pytest.param(float, float),
        pytest.param(bool, bool),
        pytest.param(str, str),
    ],
)
def test_create_primitive(type_, statement_type):
    factory = tf.TestFactory(MagicMock(TestCluster))
    result = factory._create_primitive(
        dtc.DefaultTestCase(), type_, position=0, recursion_depth=0,
    )
    assert result.variable_type == statement_type


def test_attempt_generation_for_type(test_case_mock):
    def mock_method(t, g, position, recursion_depth, allow_none):
        assert position == 0
        assert recursion_depth == 1
        assert allow_none

    factory = tf.TestFactory(MagicMock(TestCluster))
    factory.append_generic_statement = mock_method
    factory._attempt_generation_for_type(
        test_case_mock, 0, 0, True, {MagicMock(gao.GenericAccessibleObject)}
    )


def test_attempt_generation_for_no_type(test_case_mock):
    cluster = MagicMock(TestCluster)
    cluster.select_concrete_type.side_effect = lambda x: x
    factory = tf.TestFactory(cluster)
    result = factory._attempt_generation(test_case_mock, None, 0, 0, True)
    assert result is None


def test_attempt_generation_for_none_type(test_cluster_mock):
    config.INSTANCE.none_probability = 1.0
    factory = tf.TestFactory(test_cluster_mock)
    result = factory._attempt_generation(
        dtc.DefaultTestCase(), MagicMock(tf.TestFactory), 0, 0, True
    )
    assert result.distance == 0


def test_attempt_generation_for_none_type_with_no_probability(test_cluster_mock):
    config.INSTANCE.none_probability = 0.0
    factory = tf.TestFactory(test_cluster_mock)
    result = factory._attempt_generation(
        dtc.DefaultTestCase(), MagicMock(tf.TestFactory), 0, 0, True
    )
    assert result is None


def test_attempt_generation_for_type_from_cluster(test_case_mock):
    def mock_method(t, position, recursion_depth, allow_none, type_generators):
        assert position == 0
        assert recursion_depth == 0
        assert allow_none
        assert isinstance(type_generators, gao.GenericAccessibleObject)

    cluster = TestCluster()
    cluster.get_generators_for = lambda t: MagicMock(gao.GenericAccessibleObject)
    factory = tf.TestFactory(cluster)
    factory._attempt_generation_for_type = mock_method
    factory._attempt_generation(test_case_mock, MagicMock(tf.TestFactory), 0, 0, True)


def test__rollback_changes_mid():
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 10))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 15))

    cloned = test_case.clone()
    test_case.add_statement(prim.FloatPrimitiveStatement(test_case, 7.5), 1)
    assert cloned != test_case

    tf.TestFactory._rollback_changes(test_case, cloned.size(), 1)
    assert cloned == test_case


def test__rollback_changes_end():
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 10))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 15))

    cloned = test_case.clone()
    test_case.add_statement(prim.FloatPrimitiveStatement(test_case, 7.5), 3)
    assert cloned != test_case

    tf.TestFactory._rollback_changes(test_case, cloned.size(), 3)
    assert cloned == test_case


def test__rollback_changes_nothing_to_rollback():
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 10))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 15))

    cloned = test_case.clone()

    tf.TestFactory._rollback_changes(test_case, cloned.size(), 3)
    assert cloned == test_case


def test__dependencies_satisfied_no_dependencies():
    assert tf.TestFactory._dependencies_satisfied(set(), [])


def test__dependencies_satisfied_no_objects():
    assert not tf.TestFactory._dependencies_satisfied({int}, [])


def test__dependencies_satisfied_not_satisfied(test_case_mock):
    objects = [
        vri.VariableReferenceImpl(test_case_mock, int),
        vri.VariableReferenceImpl(test_case_mock, bool),
    ]
    assert not tf.TestFactory._dependencies_satisfied({int, float}, objects)


def test__dependencies_satisfied_satisfied(test_case_mock):
    objects = [
        vri.VariableReferenceImpl(test_case_mock, int),
        vri.VariableReferenceImpl(test_case_mock, bool),
    ]
    assert tf.TestFactory._dependencies_satisfied({int, bool}, objects)


def test__get_possible_calls_no_calls():
    cluster = MagicMock(TestCluster)
    cluster.get_generators_for = MagicMock(side_effect=ConstructionFailedException())
    assert tf.TestFactory(cluster)._get_possible_calls(int, []) == []


def test__get_possible_calls_single_call(test_case_mock, function_mock):
    cluster = MagicMock(TestCluster)
    cluster.get_generators_for.return_value = {function_mock}
    assert tf.TestFactory(cluster)._get_possible_calls(
        float, [vri.VariableReferenceImpl(test_case_mock, float)]
    ) == [function_mock]


def test__get_possible_calls_no_match(test_case_mock, function_mock):
    cluster = MagicMock(TestCluster)
    cluster.get_generators_for.return_value = {function_mock}
    assert (
        tf.TestFactory(cluster)._get_possible_calls(
            float, [vri.VariableReferenceImpl(test_case_mock, int)]
        )
        == []
    )


@pytest.fixture()
def sample_test_case(function_mock):
    test_case = dtc.DefaultTestCase()
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_prim2 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_function1 = par_stmt.FunctionStatement(
        test_case, function_mock, [float_prim.return_value]
    )
    float_function2 = par_stmt.FunctionStatement(
        test_case, function_mock, [float_function1.return_value]
    )
    test_case.add_statement(float_prim)
    test_case.add_statement(float_prim2)
    test_case.add_statement(float_function1)
    test_case.add_statement(float_function2)
    return test_case


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
        rec_mock.side_effect = lambda t, delete, position: delete.update({1, 2, 3})
        tf.TestFactory.delete_statement(test_case_mock, 0)
        test_case_mock.remove.assert_has_calls([call(3), call(2), call(1)])


def test_get_random_non_none_object_empty():
    test_case = dtc.DefaultTestCase()
    with pytest.raises(ConstructionFailedException):
        tf.TestFactory._get_random_non_none_object(test_case, float, 0)


def test_get_random_non_none_object_none_statement():
    test_case = dtc.DefaultTestCase()
    none_statement = prim.NoneStatement(test_case, float)
    test_case.add_statement(none_statement)
    with pytest.raises(ConstructionFailedException):
        tf.TestFactory._get_random_non_none_object(test_case, float, 0)


def test_get_random_non_none_object_success():
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 2.0)
    float1 = prim.FloatPrimitiveStatement(test_case, 3.0)
    float2 = prim.FloatPrimitiveStatement(test_case, 4.0)
    test_case.add_statement(float0)
    test_case.add_statement(float1)
    test_case.add_statement(float2)
    assert tf.TestFactory._get_random_non_none_object(test_case, float, 1) in {
        float0.return_value,
        float1.return_value,
    }


def test_get_reuse_parameters():
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float1 = prim.FloatPrimitiveStatement(test_case, 5.0)
    test_case.add_statement(float0)
    test_case.add_statement(float1)
    sign_mock = MagicMock(inspect.Signature)
    params = {"test0": float, "test1": float}
    inf_sig = MagicMock(InferredSignature, parameters=params, signature=sign_mock)
    with mock.patch("pynguin.testcase.testfactory.should_skip_parameter") as skip_mock:
        skip_mock.side_effect = [True, False]
        assert tf.TestFactory._get_reuse_parameters(test_case, inf_sig, 1) == [
            float0.return_value
        ]


def test_insert_random_statement_empty_call():
    test_case = dtc.DefaultTestCase()
    test_cluster = MagicMock(TestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.return_value = True
            assert (
                test_factory.insert_random_statement(test_case, test_case.size()) == 0
            )
            ins_mock.assert_called_with(test_case, 0)


def test_insert_random_statement_empty_on_object():
    test_case = dtc.DefaultTestCase()
    test_cluster = MagicMock(TestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 1.0
        with mock.patch.object(
            test_factory, "insert_random_call_on_object"
        ) as ins_mock:
            ins_mock.return_value = True
            assert (
                test_factory.insert_random_statement(test_case, test_case.size()) == 0
            )
            ins_mock.assert_called_with(test_case, 0)


def test_insert_random_statement_non_empty():
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_cluster = MagicMock(TestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.return_value = True
            assert test_factory.insert_random_statement(
                test_case, test_case.size()
            ) in range(test_case.size() + 1)
            assert ins_mock.call_args_list[0].args[1] in range(test_case.size() + 1)


def test_insert_random_statement_non_empty_multi_insert():
    def side_effect(tc, pos):
        tc.add_statement(prim.IntPrimitiveStatement(test_case, 5))
        tc.add_statement(prim.IntPrimitiveStatement(test_case, 5))
        return True

    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_cluster = MagicMock(TestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.side_effect = side_effect
            assert test_factory.insert_random_statement(
                test_case, test_case.size()
            ) in range(1, 1 + test_case.size() + 1)
            assert ins_mock.call_args_list[0].args[1] in range(test_case.size() + 1)


def test_insert_random_statement_no_success():
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    test_cluster = MagicMock(TestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(test_factory, "insert_random_call") as ins_mock:
            ins_mock.return_value = False
            assert (
                test_factory.insert_random_statement(test_case, test_case.size()) == -1
            )
            assert ins_mock.call_args_list[0].args[1] in range(test_case.size() + 1)


def test_insert_random_call_on_object_no_success():
    test_case = dtc.DefaultTestCase()
    test_cluster = MagicMock(TestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 0
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(
        test_factory, "_select_random_variable_for_call"
    ) as select_mock:
        select_mock.return_value = None
        assert not test_factory.insert_random_call_on_object(test_case, 0)
        select_mock.assert_called_with(test_case, 0)


def test_insert_random_call_on_object_success(variable_reference_mock):
    test_case = dtc.DefaultTestCase()
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(
        test_factory, "_select_random_variable_for_call"
    ) as select_mock:
        select_mock.return_value = variable_reference_mock
        with mock.patch.object(
            test_factory, "insert_random_call_on_object_at"
        ) as insert_mock:
            insert_mock.return_value = True
            assert test_factory.insert_random_call_on_object(test_case, 0)
            select_mock.assert_called_with(test_case, 0)
            insert_mock.assert_called_with(test_case, variable_reference_mock, 0)


def test_insert_random_call_on_object_retry(variable_reference_mock):
    test_case = dtc.DefaultTestCase()
    test_cluster = MagicMock(TestCluster)
    test_cluster.num_accessible_objects_under_test.return_value = 1
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(
        test_factory, "_select_random_variable_for_call"
    ) as select_mock:
        select_mock.return_value = variable_reference_mock
        with mock.patch.object(
            test_factory, "insert_random_call_on_object_at"
        ) as insert_random_at_mock:
            insert_random_at_mock.return_value = False
            with mock.patch.object(
                test_factory, "insert_random_call"
            ) as insert_random_mock:
                insert_random_mock.return_value = False
                assert not test_factory.insert_random_call_on_object(test_case, 0)
                select_mock.assert_called_with(test_case, 0)
                insert_random_at_mock.assert_called_with(
                    test_case, variable_reference_mock, 0
                )
                insert_random_mock.assert_called_with(test_case, 0)


def test_insert_random_call_on_object_at_no_accessible(
    test_case_mock, variable_reference_mock
):
    test_cluster = MagicMock(TestCluster)
    test_cluster.get_random_call_for.side_effect = ConstructionFailedException()
    test_factory = tf.TestFactory(test_cluster)
    variable_reference_mock.variable_type = float
    assert not test_factory.insert_random_call_on_object_at(
        test_case_mock, variable_reference_mock, 0
    )


def test_insert_random_call_on_object_at_assertion(
    test_case_mock, variable_reference_mock
):
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    variable_reference_mock.variable_type = None
    with pytest.raises(AssertionError):
        test_factory.insert_random_call_on_object_at(
            test_case_mock, variable_reference_mock, 0
        )


@pytest.mark.parametrize("result", [pytest.param(True), pytest.param(False)])
def test_insert_random_call_on_object_at_success(
    test_case_mock, variable_reference_mock, result
):
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    variable_reference_mock.variable_type = float
    with mock.patch.object(test_factory, "add_call_for") as call_mock:
        call_mock.return_value = result
        assert (
            test_factory.insert_random_call_on_object_at(
                test_case_mock, variable_reference_mock, 0
            )
            == result
        )


def test_add_call_for_field(field_mock, variable_reference_mock, test_case_mock):
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "add_field") as add_field:
        assert test_factory.add_call_for(
            test_case_mock, variable_reference_mock, field_mock, 0
        )
        add_field.assert_called_with(
            test_case_mock, field_mock, 0, callee=variable_reference_mock
        )


def test_add_call_for_method(method_mock, variable_reference_mock, test_case_mock):
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "add_method") as add_field:
        assert test_factory.add_call_for(
            test_case_mock, variable_reference_mock, method_mock, 0
        )
        add_field.assert_called_with(
            test_case_mock, method_mock, 0, callee=variable_reference_mock
        )


def test_add_call_for_rollback(method_mock, variable_reference_mock):
    def side_effect(tc, f, p, callee=None):
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5), position=p)
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5), position=p)
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5), position=p)
        raise ConstructionFailedException()

    test_case = dtc.DefaultTestCase()
    int0 = prim.IntPrimitiveStatement(test_case, 3)
    test_case.add_statement(int0)
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "add_method") as add_field:
        add_field.side_effect = side_effect
        assert not test_factory.add_call_for(
            test_case, variable_reference_mock, method_mock, 0
        )
        assert test_case.statements == [int0]


def test_add_call_for_unknown(method_mock, variable_reference_mock, test_case_mock):
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    unknown = MagicMock(gao.GenericAccessibleObject)
    unknown.is_method.return_value = False
    unknown.is_field.return_value = False
    with pytest.raises(RuntimeError):
        test_factory.add_call_for(test_case_mock, variable_reference_mock, unknown, 0)


def test_select_random_variable_for_call_one(constructor_mock, function_mock):
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.NoneStatement(test_case, MagicMock))
    test_case.add_statement(prim.FloatPrimitiveStatement(test_case, 5.0))
    function_mock.inferred_signature.update_return_type(None)
    test_case.add_statement(par_stmt.FunctionStatement(test_case, function_mock))
    const = par_stmt.ConstructorStatement(test_case, constructor_mock)
    test_case.add_statement(const)
    assert (
        tf.TestFactory._select_random_variable_for_call(test_case, test_case.size())
        == const.return_value
    )


def test_select_random_variable_for_call_none(constructor_mock, function_mock):
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.NoneStatement(test_case, MagicMock))
    test_case.add_statement(prim.FloatPrimitiveStatement(test_case, 5.0))
    function_mock.inferred_signature.update_return_type(None)
    test_case.add_statement(par_stmt.FunctionStatement(test_case, function_mock))
    assert (
        tf.TestFactory._select_random_variable_for_call(test_case, test_case.size())
        is None
    )


def test_insert_random_call_no_accessible(test_case_mock):
    test_cluster = MagicMock(TestCluster)
    test_cluster.get_random_accessible.return_value = None
    test_factory = tf.TestFactory(test_cluster)
    assert not test_factory.insert_random_call(test_case_mock, 0)


def test_insert_random_call_success(test_case_mock):
    test_cluster = MagicMock(TestCluster)
    acc = MagicMock(gao.GenericAccessibleObject)
    test_cluster.get_random_accessible.return_value = acc
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "append_generic_statement") as append_mock:
        assert test_factory.insert_random_call(test_case_mock, 0)
        append_mock.assert_called_with(test_case_mock, acc, 0)


def test_insert_random_call_rollback(test_case_mock):
    def side_effect(tc, f, p, callee=None):
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5), position=p)
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5), position=p)
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5), position=p)
        raise ConstructionFailedException()

    test_case = dtc.DefaultTestCase()
    int0 = prim.IntPrimitiveStatement(test_case, 3)
    test_case.add_statement(int0)
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(
        test_factory, "append_generic_statement"
    ) as append_generic_mock:
        append_generic_mock.side_effect = side_effect
        assert not test_factory.insert_random_call(test_case, 0)
        assert test_case.statements == [int0]


def test_delete_statement_gracefully_success(function_mock):
    test_case = dtc.DefaultTestCase()
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_prim2 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_function1 = par_stmt.FunctionStatement(
        test_case, function_mock, [float_prim2.return_value]
    )
    test_case.add_statement(float_prim)
    test_case.add_statement(float_prim2)
    test_case.add_statement(float_function1)
    assert tf.TestFactory.delete_statement_gracefully(test_case, 1)
    assert test_case.statements[1].references(float_prim.return_value)
    assert test_case.size() == 2


def test_delete_statement_gracefully_no_alternatives(function_mock):
    test_case = dtc.DefaultTestCase()
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_function1 = par_stmt.FunctionStatement(
        test_case, function_mock, [float_prim.return_value]
    )
    test_case.add_statement(float_prim)
    test_case.add_statement(float_function1)
    assert tf.TestFactory.delete_statement_gracefully(test_case, 0)
    assert test_case.size() == 0


def test_delete_statement_gracefully_no_dependencies(function_mock):
    test_case = dtc.DefaultTestCase()
    float_prim0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_prim1 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_prim2 = prim.FloatPrimitiveStatement(test_case, 5.0)
    test_case.add_statement(float_prim0)
    test_case.add_statement(float_prim1)
    test_case.add_statement(float_prim2)
    assert tf.TestFactory.delete_statement_gracefully(test_case, 1)
    assert test_case.statements == [float_prim0, float_prim2]


def test_change_random_call_unknown_type(test_case_mock):
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    assert not test_factory.change_random_call(
        test_case_mock, prim.NoneStatement(test_case_mock, None)
    )


def test_change_random_call_no_calls(function_mock):
    test_case = dtc.DefaultTestCase()
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.0)
    float_function1 = par_stmt.FunctionStatement(
        test_case, function_mock, [float_prim.return_value]
    )
    test_case.add_statement(float_prim)
    test_case.add_statement(float_function1)

    test_cluster = MagicMock(TestCluster)
    test_cluster.get_generators_for.return_value = {function_mock}
    test_factory = tf.TestFactory(test_cluster)
    assert not test_factory.change_random_call(test_case, float_function1)


def test_change_random_call_primitive(function_mock):
    test_case = dtc.DefaultTestCase()
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.0)
    test_case.add_statement(float_prim)

    test_cluster = MagicMock(TestCluster)
    test_cluster.get_generators_for.return_value = {function_mock}
    test_factory = tf.TestFactory(test_cluster)
    assert not test_factory.change_random_call(test_case, float_prim)


def test_change_random_call_success(function_mock, method_mock, constructor_mock):
    test_case = dtc.DefaultTestCase()
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.0)
    int0 = prim.IntPrimitiveStatement(test_case, 2)
    float_function1 = par_stmt.FunctionStatement(
        test_case, function_mock, [float_prim.return_value]
    )
    const = par_stmt.ConstructorStatement(test_case, constructor_mock)
    test_case.add_statement(float_prim)
    test_case.add_statement(int0)
    test_case.add_statement(const)
    test_case.add_statement(float_function1)

    test_cluster = MagicMock(TestCluster)
    test_cluster.get_generators_for.return_value = {function_mock, method_mock}
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "change_call") as change_mock:
        assert test_factory.change_random_call(test_case, float_function1)
        change_mock.assert_called_with(test_case, float_function1, method_mock)


def test_change_random_call_failed(function_mock, method_mock, constructor_mock):
    test_case = dtc.DefaultTestCase()
    float_prim = prim.FloatPrimitiveStatement(test_case, 5.0)
    int0 = prim.IntPrimitiveStatement(test_case, 2)
    float_function1 = par_stmt.FunctionStatement(
        test_case, function_mock, [float_prim.return_value]
    )
    const = par_stmt.ConstructorStatement(test_case, constructor_mock)
    test_case.add_statement(float_prim)
    test_case.add_statement(int0)
    test_case.add_statement(const)
    test_case.add_statement(float_function1)

    test_cluster = MagicMock(TestCluster)
    test_cluster.get_generators_for.return_value = {function_mock, method_mock}
    test_factory = tf.TestFactory(test_cluster)
    with mock.patch.object(test_factory, "change_call") as change_mock:
        change_mock.side_effect = ConstructionFailedException()
        assert not test_factory.change_random_call(test_case, float_function1)
        change_mock.assert_called_with(test_case, float_function1, method_mock)


def test_change_call_method(constructor_mock, method_mock):
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(par_stmt.ConstructorStatement(test_case, constructor_mock))
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 3))
    to_replace = prim.NoneStatement(test_case, float)
    test_case.add_statement(to_replace)
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    test_factory.change_call(test_case, to_replace, method_mock)
    assert test_case.statements[2].accessible_object() == method_mock
    assert test_case.statements[2].return_value is to_replace.return_value


def test_change_call_constructor(constructor_mock):
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.FloatPrimitiveStatement(test_case, 3.5))
    to_replace = prim.NoneStatement(test_case, float)
    test_case.add_statement(to_replace)
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    test_factory.change_call(test_case, to_replace, constructor_mock)
    assert test_case.statements[1].accessible_object() == constructor_mock
    assert test_case.statements[1].return_value is to_replace.return_value


def test_change_call_function(function_mock):
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.FloatPrimitiveStatement(test_case, 3.5))
    to_replace = prim.NoneStatement(test_case, float)
    test_case.add_statement(to_replace)
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    test_factory.change_call(test_case, to_replace, function_mock)
    assert test_case.statements[1].accessible_object() == function_mock
    assert test_case.statements[1].return_value is to_replace.return_value


def test_change_call_unknown():
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim.FloatPrimitiveStatement(test_case, 3.5))
    to_replace = prim.NoneStatement(test_case, float)
    test_case.add_statement(to_replace)
    test_cluster = MagicMock(TestCluster)
    test_factory = tf.TestFactory(test_cluster)
    acc = MagicMock(gao.GenericAccessibleObject)
    acc.is_method.return_value = False
    acc.is_constructor.return_value = False
    acc.is_function.return_value = False
    with pytest.raises(AssertionError):
        test_factory.change_call(test_case, to_replace, acc)


def test_create_or_reuse_variable_no_guessing(test_case_mock):
    cluster = MagicMock(TestCluster)
    factory = tf.TestFactory(cluster)
    config.INSTANCE.guess_unknown_types = False
    assert factory._create_or_reuse_variable(test_case_mock, None, 1, 1, True) is None
