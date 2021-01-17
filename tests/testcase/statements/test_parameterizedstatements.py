#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.variable.variablereferenceimpl as vri


def test_constructor_statement_no_args(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert statement.args == []
    assert statement.kwargs == {}


def test_constructor_statement_args(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = ps.ConstructorStatement(test_case_mock, constructor_mock)
    references = [
        MagicMock(vri.VariableReferenceImpl),
        MagicMock(vri.VariableReferenceImpl),
    ]
    statement.args = references
    assert statement.args == references


def test_constructor_statement_kwargs(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = ps.ConstructorStatement(test_case_mock, constructor_mock)
    references = {
        "par1": MagicMock(vri.VariableReferenceImpl),
        "par2": MagicMock(vri.VariableReferenceImpl),
    }
    statement.kwargs = references
    assert statement.kwargs == references


def test_constructor_statement_accept(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = ps.ConstructorStatement(test_case_mock, constructor_mock)
    visitor = MagicMock(sv.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_constructor_statement.assert_called_once_with(statement)


def test_constructor_statement_hash(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert statement.__hash__() != 0


def test_constructor_statement_eq_same(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert statement.__eq__(statement)


def test_constructor_statement_eq_other_type(
    test_case_mock, variable_reference_mock, constructor_mock
):
    statement = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert not statement.__eq__(variable_reference_mock)


def test_constructor_replace_kwargs(constructor_mock):
    test_case = dtc.DefaultTestCase()
    int0 = prim.IntPrimitiveStatement(test_case, 0)
    int1 = prim.IntPrimitiveStatement(test_case, 0)
    new_value = prim.IntPrimitiveStatement(test_case, 0)
    const = ps.ConstructorStatement(
        test_case,
        constructor_mock,
        kwargs={"test": int0.ret_val, "test2": int1.ret_val},
    )
    test_case.add_statement(int0)
    test_case.add_statement(int1)
    test_case.add_statement(new_value)
    test_case.add_statement(const)
    const.replace(int0.ret_val, new_value.ret_val)
    assert const.kwargs == {"test": new_value.ret_val, "test2": int1.ret_val}


def test_constructor_replace_args(constructor_mock):
    test_case = dtc.DefaultTestCase()
    int0 = prim.IntPrimitiveStatement(test_case, 0)
    new_value = prim.IntPrimitiveStatement(test_case, 0)
    const = ps.ConstructorStatement(test_case, constructor_mock, args=[int0.ret_val])
    test_case.add_statement(int0)
    test_case.add_statement(new_value)
    test_case.add_statement(const)
    const.replace(int0.ret_val, new_value.ret_val)
    assert const.args == [new_value.ret_val]


def test_constructor_replace_return_value(constructor_mock):
    test_case = dtc.DefaultTestCase()
    new_value = prim.IntPrimitiveStatement(test_case, 0)
    const = ps.ConstructorStatement(test_case, constructor_mock)
    test_case.add_statement(new_value)
    test_case.add_statement(const)
    const.replace(const.ret_val, new_value.ret_val)
    assert const.ret_val == new_value.ret_val


def test_constructor_clone_kwargs(constructor_mock):
    test_case = dtc.DefaultTestCase()
    new_test_case = dtc.DefaultTestCase()
    to_clone = MagicMock(vri.VariableReferenceImpl)
    the_clone = MagicMock(vri.VariableReferenceImpl)
    to_clone.clone.return_value = the_clone
    const = ps.ConstructorStatement(
        test_case, constructor_mock, kwargs={"test": to_clone}
    )
    assert const._clone_kwargs(new_test_case, 10) == {"test": the_clone}
    to_clone.clone.assert_called_with(new_test_case, 10)


def test_constructor_clone_args(constructor_mock):
    test_case = dtc.DefaultTestCase()
    new_test_case = dtc.DefaultTestCase()
    to_clone = MagicMock(vri.VariableReferenceImpl)
    the_clone = MagicMock(vri.VariableReferenceImpl)
    to_clone.clone.return_value = the_clone
    const = ps.ConstructorStatement(test_case, constructor_mock, [to_clone])
    assert const._clone_args(new_test_case, 10) == [the_clone]
    to_clone.clone.assert_called_with(new_test_case, 10)


def test_constructor_mutate_no_mutation(constructor_mock, test_case_mock):
    config.INSTANCE.change_parameter_probability = 0.0
    const = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert not const.mutate()


def test_constructor_mutate_nothing_to_mutate(constructor_mock, test_case_mock):
    config.INSTANCE.change_parameter_probability = 1.0
    const = ps.ConstructorStatement(test_case_mock, constructor_mock)
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
def test_constructor_mutate_simple(
    constructor_mock, test_case_mock, s_param, param, result
):
    config.INSTANCE.change_parameter_probability = 1.0
    const = ps.ConstructorStatement(test_case_mock, constructor_mock)
    with mock.patch.object(const, "_mutable_argument_count") as arg_count:
        arg_count.return_value = 5
        with mock.patch.object(
            const, "_mutate_special_parameters"
        ) as mutate_special_paramaters:
            mutate_special_paramaters.return_value = s_param
            with mock.patch.object(const, "_mutate_parameters") as mutate_parameters:
                mutate_parameters.return_value = param
                assert const.mutate() == result
                arg_count.assert_called_once()
                mutate_special_paramaters.assert_called_with(0.2)
                mutate_parameters.assert_called_with(0.2)


def test_constructor_mutable_arg_count(test_case_mock, constructor_mock):
    const = ps.ConstructorStatement(
        test_case_mock,
        constructor_mock,
        [MagicMock(vri.VariableReferenceImpl)],
        {"test": MagicMock(vri.VariableReferenceImpl)},
    )
    assert const._mutable_argument_count() == 2


def test_constructor_mutate_special_parameters(test_case_mock, constructor_mock):
    const = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert not const._mutate_special_parameters(1.0)


def test_constructor_mutate_parameters_nothing(test_case_mock, constructor_mock):
    const = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert not const._mutate_parameters(1.0)


def test_constructor_mutate_parameters_args(
    test_case_mock, constructor_mock, variable_reference_mock
):
    const = ps.ConstructorStatement(
        test_case_mock,
        constructor_mock,
        [variable_reference_mock, variable_reference_mock],
    )
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        with mock.patch.object(const, "_mutate_parameter") as mutate_parameter:
            mutate_parameter.return_value = True
            float_mock.side_effect = [0.0, 1.0]
            assert const._mutate_parameters(0.5)
            mutate_parameter.assert_called_with(0)


def test_constructor_mutate_parameters_kwargs(
    test_case_mock, constructor_mock, variable_reference_mock
):
    const = ps.ConstructorStatement(
        test_case_mock,
        constructor_mock,
        kwargs={"test": variable_reference_mock, "test2": variable_reference_mock},
    )
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        with mock.patch.object(const, "_mutate_parameter") as mutate_parameter:
            mutate_parameter.return_value = True
            float_mock.side_effect = [0.0, 1.0]
            assert const._mutate_parameters(0.5)
            mutate_parameter.assert_called_with("test")


def test_constructor_mutate_parameter_get_objects(constructor_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    const = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    test_case.add_statement(float0)
    test_case.add_statement(const)
    with mock.patch.object(const, "_test_case") as tc:
        tc.get_objects.return_value = [float0.ret_val]
        assert const._mutate_parameter(0)
        tc.get_objects.assert_called_with(
            float0.ret_val.variable_type, const.get_position()
        )


def test_constructor_mutate_parameter_not_included(constructor_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    const = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    test_case.add_statement(float0)
    test_case.add_statement(const)
    with mock.patch.object(test_case, "get_objects") as get_objs:
        get_objs.return_value = []
        assert const._mutate_parameter(0)
        get_objs.assert_called_with(float0.ret_val.variable_type, 1)
        assert isinstance(
            test_case.get_statement(const.args[0].get_statement_position()),
            prim.NoneStatement,
        )


def test_constructor_mutate_parameter_add_copy(constructor_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    const = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    test_case.add_statement(float0)
    test_case.add_statement(const)
    with mock.patch.object(const, "_param_count_of_type") as param_count_of_type:
        with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
            choice_mock.side_effect = lambda coll: coll[0]
            param_count_of_type.return_value = 5
            assert const._mutate_parameter(0)
            param_count_of_type.assert_called_with(float0.ret_val.variable_type)
            assert const.args[0] != float0.ret_val


def test_constructor_mutate_parameter_choose_none(constructor_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    const = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    test_case.add_statement(float0)
    test_case.add_statement(const)
    assert const._mutate_parameter(0)
    assert isinstance(
        test_case.get_statement(const.args[0].get_statement_position()),
        prim.NoneStatement,
    )


def test_constructor_mutate_parameter_choose_existing(constructor_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float1 = prim.FloatPrimitiveStatement(test_case, 5.0)
    const = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    test_case.add_statement(float0)
    test_case.add_statement(float1)
    test_case.add_statement(const)
    with mock.patch("pynguin.utils.randomness.choice") as choice_mock:
        choice_mock.side_effect = lambda coll: coll[0]
        assert const._mutate_parameter(0)


def test_constructor_param_count_of_type_none(test_case_mock, constructor_mock):
    const = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert const._param_count_of_type(None) == 0


def test_constructor_param_count_of_type(test_case_mock, constructor_mock):
    const = ps.ConstructorStatement(
        test_case_mock,
        constructor_mock,
        [
            vri.VariableReferenceImpl(test_case_mock, float),
            vri.VariableReferenceImpl(test_case_mock, int),
        ],
        {
            "test0": vri.VariableReferenceImpl(test_case_mock, float),
            "test1": vri.VariableReferenceImpl(test_case_mock, int),
        },
    )
    assert const._param_count_of_type(float) == 2


def test_constructor_get_argument(test_case_mock, constructor_mock):
    var0 = vri.VariableReferenceImpl(test_case_mock, float)
    var1 = vri.VariableReferenceImpl(test_case_mock, float)
    var2 = vri.VariableReferenceImpl(test_case_mock, float)
    var3 = vri.VariableReferenceImpl(test_case_mock, float)
    const = ps.ConstructorStatement(
        test_case_mock, constructor_mock, [var0, var1], {"test0": var2, "test1": var3}
    )
    assert const._get_argument(0) is var0
    assert const._get_argument("test0") is var2


def test_constructor_replace_argument(test_case_mock, constructor_mock):
    var0 = vri.VariableReferenceImpl(test_case_mock, float)
    var1 = vri.VariableReferenceImpl(test_case_mock, float)
    var2 = vri.VariableReferenceImpl(test_case_mock, float)
    var3 = vri.VariableReferenceImpl(test_case_mock, float)
    const = ps.ConstructorStatement(
        test_case_mock, constructor_mock, [var0], {"test0": var2}
    )
    const._replace_argument(0, var1)
    assert const.args[0] is var1
    const._replace_argument("test0", var3)
    assert const.kwargs["test0"] is var3


def test_constructor_get_accessible_object(test_case_mock, constructor_mock):
    const = ps.ConstructorStatement(test_case_mock, constructor_mock)
    assert const.accessible_object() == constructor_mock


def test_method_statement_no_args(test_case_mock, variable_reference_mock, method_mock):
    statement = ps.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    assert statement.args == []
    assert statement.kwargs == {}


def test_method_statement_args(test_case_mock, variable_reference_mock, method_mock):
    references = [
        MagicMock(vri.VariableReferenceImpl),
        MagicMock(vri.VariableReferenceImpl),
    ]

    statement = ps.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    statement.args = references
    assert statement.args == references


def test_method_statement_kwargs(test_case_mock, variable_reference_mock, method_mock):
    references = {
        "par1": MagicMock(vri.VariableReferenceImpl),
        "par2": MagicMock(vri.VariableReferenceImpl),
    }

    statement = ps.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    statement.kwargs = references
    assert statement.kwargs == references


def test_method_statement_accept(test_case_mock, variable_reference_mock, method_mock):
    statement = ps.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    visitor = MagicMock(sv.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_method_statement.assert_called_once_with(statement)


def test_method_get_accessible_object(
    test_case_mock, method_mock, variable_reference_mock
):
    meth = ps.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    assert meth.accessible_object() == method_mock


def test_method_mutable_argument_count(
    test_case_mock, method_mock, variable_reference_mock
):
    meth = ps.MethodStatement(
        test_case_mock,
        method_mock,
        variable_reference_mock,
        [variable_reference_mock],
        {"test": variable_reference_mock},
    )
    assert meth._mutable_argument_count() == 3


def test_method_mutate_special_parameters_no_mutation(
    test_case_mock, method_mock, variable_reference_mock
):
    meth = ps.MethodStatement(test_case_mock, method_mock, variable_reference_mock)
    assert not meth._mutate_special_parameters(0.0)


def test_method_mutate_special_parameters_none_found(method_mock, constructor_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    const0 = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    int0 = prim.IntPrimitiveStatement(test_case, 5)
    meth = ps.MethodStatement(test_case, method_mock, const0.ret_val)
    test_case.add_statement(float0)
    test_case.add_statement(const0)
    test_case.add_statement(int0)
    test_case.add_statement(meth)
    with mock.patch.object(meth, "_test_case") as tc:
        tc.get_objects.return_value = [const0.ret_val]
        assert not meth._mutate_special_parameters(1.0)
        tc.get_objects.assert_called_with(
            const0.ret_val.variable_type, meth.get_position()
        )


def test_method_mutate_special_parameters_one_found(method_mock, constructor_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 5.0)
    const0 = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    const1 = ps.ConstructorStatement(test_case, constructor_mock, [float0.ret_val])
    int0 = prim.IntPrimitiveStatement(test_case, 5)
    meth = ps.MethodStatement(test_case, method_mock, const0.ret_val)
    test_case.add_statement(float0)
    test_case.add_statement(const0)
    test_case.add_statement(const1)
    test_case.add_statement(int0)
    test_case.add_statement(meth)
    with mock.patch.object(meth, "_test_case") as tc:
        tc.get_objects.return_value = [const0.ret_val, const1.ret_val]
        assert meth._mutate_special_parameters(1.0)
        tc.get_objects.assert_called_with(
            const0.ret_val.variable_type, meth.get_position()
        )
        assert meth.callee == const1.ret_val


def test_method_get_variable_references(method_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 0.0)
    float1 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float2 = prim.FloatPrimitiveStatement(test_case, 10.0)
    meth = ps.MethodStatement(
        test_case,
        method_mock,
        float2.ret_val,
        args=[float0.ret_val],
        kwargs={"test": float1.ret_val},
    )
    test_case.add_statement(float0)
    test_case.add_statement(float1)
    test_case.add_statement(float2)
    test_case.add_statement(meth)
    assert meth.get_variable_references() == {
        float0.ret_val,
        float1.ret_val,
        float2.ret_val,
        meth.ret_val,
    }


def test_method_get_variable_replace(method_mock):
    test_case = dtc.DefaultTestCase()
    float0 = prim.FloatPrimitiveStatement(test_case, 0.0)
    float1 = prim.FloatPrimitiveStatement(test_case, 5.0)
    float2 = prim.FloatPrimitiveStatement(test_case, 10.0)
    float3 = prim.FloatPrimitiveStatement(test_case, 10.0)
    meth = ps.MethodStatement(
        test_case,
        method_mock,
        float2.ret_val,
        args=[float0.ret_val],
        kwargs={"test": float1.ret_val},
    )
    test_case.add_statement(float0)
    test_case.add_statement(float1)
    test_case.add_statement(float2)
    test_case.add_statement(float3)
    test_case.add_statement(meth)
    meth.replace(float2.ret_val, float3.ret_val)
    meth.replace(float1.ret_val, float3.ret_val)
    assert meth.callee == float3.ret_val


def test_function_accessible_object(test_case_mock, function_mock):
    func = ps.FunctionStatement(test_case_mock, function_mock)
    assert func.accessible_object() == function_mock
