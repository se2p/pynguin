#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import inspect
import operator

from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.statement as stmt
import pynguin.testcase.variablereference as vr

from pynguin.analyses.typesystem import AnyType
from pynguin.analyses.typesystem import InferredSignature
from pynguin.utils.generic.genericaccessibleobject import GenericFunction


def test_constructor_statement_no_args(default_test_case, constructor_mock):
    statement = stmt.ConstructorStatement(default_test_case, constructor_mock)
    assert statement.args == {}


def test_constructor_statement_args(default_test_case, constructor_mock):
    statement = stmt.ConstructorStatement(default_test_case, constructor_mock)
    references = {
        "a": MagicMock(vr.VariableReference),
        "b": MagicMock(vr.VariableReference),
    }
    statement.args = references
    assert statement.args == references


def test_constructor_statement_accept(test_case_mock, constructor_mock):
    statement = stmt.ConstructorStatement(test_case_mock, constructor_mock)
    visitor = MagicMock(stmt.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_constructor_statement.assert_called_once_with(statement)


def test_constructor_statement_hash(test_case_mock, constructor_mock):
    statement = stmt.ConstructorStatement(test_case_mock, constructor_mock)
    assert statement.structural_hash({statement.ret_val: 0}) != 0


def test_constructor_statement_eq_same(test_case_mock, constructor_mock):
    statement = stmt.ConstructorStatement(test_case_mock, constructor_mock)
    assert statement.structural_eq(statement, {statement.ret_val: statement.ret_val})


def test_function_different_callables_different_hashes(
    default_test_case, function_mock, type_system
):
    def other_function(z: float) -> float:
        return z  # pragma: no cover

    other = GenericFunction(
        function=other_function,
        inferred_signature=InferredSignature(
            signature=inspect.Signature(
                parameters=[
                    inspect.Parameter(
                        name="z",
                        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=float,
                    ),
                ]
            ),
            original_return_type=type_system.convert_type_hint(float),
            original_parameters={"z": type_system.convert_type_hint(float)},
            type_system=type_system,
        ),
    )
    function_statement = stmt.FunctionStatement(default_test_case, function_mock, {})
    other_statement = stmt.FunctionStatement(default_test_case, other, {})
    assert not function_statement.structural_eq(
        other_statement, {function_statement.ret_val: function_statement.ret_val}
    )
    assert not other_statement.structural_eq(
        function_statement, {other_statement.ret_val: other_statement.ret_val}
    )
    assert function_statement.structural_hash({
        function_statement.ret_val: 0
    }) != other_statement.structural_hash({other_statement.ret_val: 0})


def test_constructor_statement_eq_other_type(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = stmt.ConstructorStatement(test_case_mock, constructor_mock)
    assert not statement.structural_eq(variable_reference_mock, {})


def test_constructor_replace_args(constructor_mock, default_test_case):
    int0 = stmt.IntPrimitiveStatement(default_test_case, 0)
    new_value = stmt.IntPrimitiveStatement(default_test_case, 0)
    const = stmt.ConstructorStatement(default_test_case, constructor_mock, {"a": int0.ret_val})
    default_test_case.add_statement(int0)
    default_test_case.add_statement(new_value)
    default_test_case.add_statement(const)
    const.replace(int0.ret_val, new_value.ret_val)
    assert const.args == {"a": new_value.ret_val}


def test_constructor_replace_return_value(constructor_mock, default_test_case):
    new_value = stmt.IntPrimitiveStatement(default_test_case, 0)
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    default_test_case.add_statement(new_value)
    default_test_case.add_statement(const)
    const.replace(const.ret_val, new_value.ret_val)
    assert const.ret_val == new_value.ret_val


def test_constructor_clone_args(constructor_mock, default_test_case):
    ref = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(float),
    )
    clone = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(float),
    )
    const = stmt.ConstructorStatement(default_test_case, constructor_mock, {"a": ref})
    assert const._clone_args({ref: clone}) == {"a": clone}


def test_constructor_mutate_no_mutation(constructor_mock, default_test_case):
    config.configuration.search_algorithm.change_parameter_probability = 0.0
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    assert not const.mutate()


def test_constructor_mutate_nothing_to_mutate(constructor_mock, default_test_case):
    config.configuration.search_algorithm.change_parameter_probability = 1.0
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    assert not const.mutate()


@pytest.mark.parametrize(
    "s_param,param,result",
    [
        pytest.param(True, True, True),
        pytest.param(False, True, True),
        pytest.param(True, False, True),
        pytest.param(False, False, False),
    ],
)
def test_constructor_mutate_simple(constructor_mock, default_test_case, s_param, param, result):
    config.configuration.search_algorithm.change_parameter_probability = 1.0
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    with mock.patch.object(const, "_mutable_argument_count") as arg_count:
        arg_count.return_value = 5
        with mock.patch.object(const, "_mutate_special_parameters") as mutate_special_parameters:
            mutate_special_parameters.return_value = s_param
            with mock.patch.object(const, "_mutate_parameters") as mutate_parameters:
                mutate_parameters.return_value = param
                assert const.mutate() == result
                arg_count.assert_called_once()
                mutate_special_parameters.assert_called_with(0.2)
                mutate_parameters.assert_called_with(0.2)


def test_constructor_mutable_arg_count(test_case_mock, constructor_mock):
    const = stmt.ConstructorStatement(
        test_case_mock,
        constructor_mock,
        {"test": MagicMock(vr.VariableReference)},
    )
    assert const._mutable_argument_count() == 1


def test_constructor_mutate_special_parameters(test_case_mock, constructor_mock):
    const = stmt.ConstructorStatement(test_case_mock, constructor_mock)
    assert not const._mutate_special_parameters(1.0)


def test_constructor_mutate_parameters_nothing(test_case_mock, variable_reference_mock):
    const = stmt.ConstructorStatement(
        test_case_mock,
        MagicMock(inferred_signature=MagicMock(parameters={"a": float, "b": int})),
        {"a": variable_reference_mock, "b": variable_reference_mock},
    )
    assert not const._mutate_parameters(0.0)


def test_constructor_mutate_parameters_args(test_case_mock, variable_reference_mock):
    signature = MagicMock(original_parameters={"a": float, "b": int})
    const = stmt.ConstructorStatement(
        test_case_mock,
        MagicMock(inferred_signature=signature),
        {"a": variable_reference_mock, "b": variable_reference_mock},
    )
    with mock.patch(  # noqa: SIM117
        "pynguin.utils.randomness.next_float"
    ) as float_mock:
        with mock.patch.object(const, "_mutate_parameter") as mutate_parameter:
            mutate_parameter.return_value = True
            float_mock.side_effect = [0.0, 1.0]
            assert const._mutate_parameters(0.5)
            mutate_parameter.assert_called_with("a", signature)


def test_constructor_mutate_parameter_get_objects(constructor_mock, default_test_case):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    const = stmt.ConstructorStatement(default_test_case, constructor_mock, {"y": float0.ret_val})
    default_test_case.add_statement(float0)
    default_test_case.add_statement(const)
    with mock.patch.object(const, "_test_case") as tc:
        tc.get_objects.return_value = [float0.ret_val]
        tc.statements = [float0, const]
        with mock.patch("pynguin.testcase.statement.is_optional_parameter") as optional_mock:
            optional_mock.return_value = False
            # fmt: off
            assert const._mutate_parameter(
                "y",
                InferredSignature(
                    signature=constructor_mock.inferred_signature.signature,
                    original_parameters={
                        "y": default_test_case.test_cluster.type_system
                        .convert_type_hint(float)
                    },
                    original_return_type=default_test_case.test_cluster.type_system
                    .convert_type_hint(None),
                    type_system=default_test_case.test_cluster.type_system,
                ),
            )
            # fmt: on
            tc.get_objects.assert_called_with(float0.ret_val.type, const.get_position())


def test_constructor_mutate_parameter_not_included(constructor_mock, default_test_case):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    const = stmt.ConstructorStatement(default_test_case, constructor_mock, {"y": float0.ret_val})
    default_test_case.add_statement(float0)
    default_test_case.add_statement(const)
    with mock.patch.object(default_test_case, "get_objects") as get_objs:
        get_objs.return_value = []
        with mock.patch("pynguin.testcase.statement.is_optional_parameter") as optional_mock:
            optional_mock.return_value = False
            # fmt: off
            assert const._mutate_parameter(
                "y",
                InferredSignature(
                    signature=constructor_mock.inferred_signature.signature,
                    original_parameters={
                        "y": default_test_case.test_cluster.type_system
                        .convert_type_hint(float)
                    },
                    original_return_type=default_test_case.test_cluster.type_system
                    .convert_type_hint(None),
                    type_system=default_test_case.test_cluster.type_system,
                ),
            )
            # fmt: on
            get_objs.assert_called_with(float0.ret_val.type, 1)
            assert isinstance(
                default_test_case.get_statement(const.args["y"].get_statement_position()),
                stmt.NoneStatement,
            )


def test_constructor_mutate_parameter_add_copy(constructor_mock, default_test_case):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    const = stmt.ConstructorStatement(default_test_case, constructor_mock, {"y": float0.ret_val})
    default_test_case.add_statement(float0)
    default_test_case.add_statement(const)
    with mock.patch.object(  # noqa: SIM117
        const, "_param_count_of_type"
    ) as param_count_of_type:
        with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
            choice_mock.side_effect = operator.itemgetter(0)
            param_count_of_type.return_value = 5
            with mock.patch("pynguin.testcase.statement.is_optional_parameter") as optional_mock:
                optional_mock.return_value = False
                # fmt: off
                assert const._mutate_parameter(
                    "y",
                    InferredSignature(
                        signature=constructor_mock.inferred_signature.signature,
                        original_parameters={
                            "y": default_test_case.test_cluster.type_system
                            .convert_type_hint(float)
                        },
                        original_return_type=default_test_case.test_cluster.type_system
                        .convert_type_hint(None),
                        type_system=default_test_case.test_cluster.type_system,
                    ),
                )
                # fmt: on
                param_count_of_type.assert_called_with(float0.ret_val.type)
                assert const.args["y"] != float0.ret_val


def test_constructor_mutate_parameter_choose_none(constructor_mock, default_test_case):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    const = stmt.ConstructorStatement(default_test_case, constructor_mock, {"a": float0.ret_val})
    default_test_case.add_statement(float0)
    default_test_case.add_statement(const)
    with mock.patch("pynguin.testcase.testfactory.is_optional_parameter") as optional_mock:
        optional_mock.return_value = False
        assert const._mutate_parameter(
            "a",
            MagicMock(
                parameters={
                    "a": default_test_case.test_cluster.type_system.convert_type_hint(float)
                }
            ),
        )
        assert isinstance(
            default_test_case.get_statement(const.args["a"].get_statement_position()),
            stmt.NoneStatement,
        )


def test_constructor_mutate_parameter_choose_existing(constructor_mock, default_test_case):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float1 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    const = stmt.ConstructorStatement(default_test_case, constructor_mock, {"a": float0.ret_val})
    default_test_case.add_statement(float0)
    default_test_case.add_statement(float1)
    default_test_case.add_statement(const)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = operator.itemgetter(0)
        with mock.patch("pynguin.testcase.testfactory.is_optional_parameter") as optional_mock:
            optional_mock.return_value = False
            # fmt: off
            assert const._mutate_parameter(
                "a",
                MagicMock(
                    parameters={
                        "a": default_test_case.test_cluster.type_system
                        .convert_type_hint(float)
                    }
                ),
            )
            # fmt: on


def test_constructor_param_count_of_type_none(default_test_case, constructor_mock):
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    assert const._param_count_of_type(AnyType()) == 0


def test_constructor_param_count_of_type(default_test_case, constructor_mock):
    const = stmt.ConstructorStatement(
        default_test_case,
        constructor_mock,
        {
            "test0": vr.VariableReference(
                default_test_case,
                default_test_case.test_cluster.type_system.convert_type_hint(float),
            ),
            "test1": vr.VariableReference(
                default_test_case,
                default_test_case.test_cluster.type_system.convert_type_hint(int),
            ),
        },
    )
    assert (
        const._param_count_of_type(
            default_test_case.test_cluster.type_system.convert_type_hint(float)
        )
        == 1
    )


def test_constructor_get_accessible_object(test_case_mock, constructor_mock):
    const = stmt.ConstructorStatement(test_case_mock, constructor_mock)
    assert const.accessible_object() == constructor_mock


def test_method_statement_no_args(test_case_mock, variable_reference_mock, method_mock):
    statement = stmt.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    assert statement.args == {}


def test_method_statement_args(test_case_mock, variable_reference_mock, method_mock):
    references = {
        "a": MagicMock(vr.VariableReference),
        "b": MagicMock(vr.VariableReference),
    }

    statement = stmt.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    statement.args = references
    assert statement.args == references


def test_method_statement_not_eq(default_test_case, method_mock):
    var1 = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(MagicMock),
    )
    var2 = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(MagicMock),
    )

    args = {
        "a": var1,
    }

    statement = stmt.MethodStatement(default_test_case, method_mock, var1, args)
    statement2 = stmt.MethodStatement(default_test_case, method_mock, var2, args)
    assert not statement.structural_eq(
        statement2, {statement.ret_val: statement2.ret_val, var1: var1, var2: var2}
    )


def test_method_statement_eq(default_test_case, method_mock):
    var1 = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(MagicMock),
    )
    var2 = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(MagicMock),
    )

    args = {
        "a": var1,
    }

    statement = stmt.MethodStatement(default_test_case, method_mock, var1, args)
    statement2 = stmt.MethodStatement(default_test_case, method_mock, var1, args)
    assert statement.structural_eq(
        statement2, {statement.ret_val: statement2.ret_val, var1: var1, var2: var2}
    )
    assert statement.structural_hash({
        var1: 0,
        statement.ret_val: 1,
    }) == statement2.structural_hash({var1: 0, statement2.ret_val: 1})


def test_method_statement_accept(default_test_case, variable_reference_mock, method_mock):
    statement = stmt.MethodStatement(default_test_case, method_mock, variable_reference_mock)
    visitor = MagicMock(stmt.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_method_statement.assert_called_once_with(statement)


def test_method_get_accessible_object(default_test_case, method_mock, variable_reference_mock):
    meth = stmt.MethodStatement(default_test_case, method_mock, variable_reference_mock)
    assert meth.accessible_object() == method_mock


def test_method_mutable_argument_count(default_test_case, method_mock, variable_reference_mock):
    meth = stmt.MethodStatement(
        default_test_case,
        method_mock,
        variable_reference_mock,
        {"test": variable_reference_mock},
    )
    assert meth._mutable_argument_count() == 2


def test_method_mutate_special_parameters_no_mutation(
    default_test_case, method_mock, variable_reference_mock
):
    meth = stmt.MethodStatement(default_test_case, method_mock, variable_reference_mock)
    assert not meth._mutate_special_parameters(0.0)


def test_method_mutate_special_parameters_none_found(
    method_mock, constructor_mock, default_test_case
):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    const0 = stmt.ConstructorStatement(default_test_case, constructor_mock, {"a": float0.ret_val})
    int0 = stmt.IntPrimitiveStatement(default_test_case, 5)
    meth = stmt.MethodStatement(default_test_case, method_mock, const0.ret_val)
    default_test_case.add_statement(float0)
    default_test_case.add_statement(const0)
    default_test_case.add_statement(int0)
    default_test_case.add_statement(meth)
    with mock.patch.object(meth, "_test_case") as tc:
        tc.get_objects.return_value = [const0.ret_val]
        tc.statements = [float0, const0, int0, meth]
        assert not meth._mutate_special_parameters(1.0)
        tc.get_objects.assert_called_with(const0.ret_val.type, meth.get_position())


def test_method_mutate_special_parameters_one_found(
    method_mock, constructor_mock, default_test_case
):
    float0 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    const0 = stmt.ConstructorStatement(default_test_case, constructor_mock, {"a": float0.ret_val})
    const1 = stmt.ConstructorStatement(default_test_case, constructor_mock, {"a": float0.ret_val})
    int0 = stmt.IntPrimitiveStatement(default_test_case, 5)
    meth = stmt.MethodStatement(default_test_case, method_mock, const0.ret_val)
    default_test_case.add_statement(float0)
    default_test_case.add_statement(const0)
    default_test_case.add_statement(const1)
    default_test_case.add_statement(int0)
    default_test_case.add_statement(meth)
    with mock.patch.object(meth, "_test_case") as tc:
        tc.get_objects.return_value = [const0.ret_val, const1.ret_val]
        tc.statements = [float0, const0, const1, int0, meth]
        assert meth._mutate_special_parameters(1.0)
        tc.get_objects.assert_called_with(const0.ret_val.type, meth.get_position())
        assert meth.callee == const1.ret_val


def test_method_get_variable_references(method_mock, default_test_case):
    float1 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float2 = stmt.FloatPrimitiveStatement(default_test_case, 10.0)
    meth = stmt.MethodStatement(
        default_test_case,
        method_mock,
        float2.ret_val,
        args={"test": float1.ret_val},
    )
    default_test_case.add_statement(float1)
    default_test_case.add_statement(float2)
    default_test_case.add_statement(meth)
    assert meth.get_variable_references() == {
        float1.ret_val,
        float2.ret_val,
        meth.ret_val,
    }


def test_method_get_variable_replace(method_mock, default_test_case):
    float1 = stmt.FloatPrimitiveStatement(default_test_case, 5.0)
    float2 = stmt.FloatPrimitiveStatement(default_test_case, 10.0)
    float3 = stmt.FloatPrimitiveStatement(default_test_case, 10.0)
    meth = stmt.MethodStatement(
        default_test_case,
        method_mock,
        float2.ret_val,
        args={"test": float1.ret_val},
    )
    default_test_case.add_statement(float1)
    default_test_case.add_statement(float2)
    default_test_case.add_statement(float3)
    default_test_case.add_statement(meth)
    meth.replace(float2.ret_val, float3.ret_val)
    meth.replace(float1.ret_val, float3.ret_val)
    assert meth.callee == float3.ret_val


def test_function_accessible_object(default_test_case, function_mock):
    func = stmt.FunctionStatement(default_test_case, function_mock)
    assert func.accessible_object() == function_mock
