#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock, call

import pytest

import pynguin.assertion.primitiveassertion as pas
import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statement as st
import pynguin.testcase.testfactory as tf
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
from pynguin.testcase.execution.executionresult import ExecutionResult


@pytest.fixture
def default_test_case():
    # TODO what about the logger, should be a mock
    return dtc.DefaultTestCase()


def get_default_test_case():
    return dtc.DefaultTestCase()


def test_add_statement_end(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    stmt_3.return_value = MagicMock(vr.VariableReference)
    default_test_case._statements.extend([stmt_1, stmt_2])

    reference = default_test_case.add_statement(stmt_3)
    assert reference
    assert default_test_case._statements == [stmt_1, stmt_2, stmt_3]


def test_add_statement_middle(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_2.return_value = MagicMock(vr.VariableReference)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_3])

    reference = default_test_case.add_statement(stmt_2, position=1)
    assert reference
    assert default_test_case._statements == [stmt_1, stmt_2, stmt_3]


def test_add_statements(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.append(stmt_1)
    default_test_case.add_statements([stmt_2, stmt_3])
    assert default_test_case._statements == [stmt_1, stmt_2, stmt_3]


def test_id(default_test_case):
    assert default_test_case.id >= 0


def test_chop(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    default_test_case.chop(1)
    assert default_test_case._statements == [stmt_1, stmt_2]


def test_contains_true(default_test_case):
    stmt = MagicMock(st.Statement)
    default_test_case._statements.append(stmt)
    assert default_test_case.contains(stmt)


def test_contains_false(default_test_case):
    assert not default_test_case.contains(MagicMock(st.Statement))


def test_size(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    assert default_test_case.size() == 3


def test_remove_nothing(default_test_case):
    default_test_case.remove(1)


def test_remove(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    default_test_case.remove(1)
    assert default_test_case._statements == [stmt_1, stmt_3]


def test_get_statement(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    assert default_test_case.get_statement(1) == stmt_2


def test_get_statement_negative_position(default_test_case):
    with pytest.raises(AssertionError):
        default_test_case.get_statement(-1)


def test_get_statement_positive_position(default_test_case):
    with pytest.raises(AssertionError):
        default_test_case.get_statement(42)


def test_has_statement(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    stmt_2 = MagicMock(st.Statement)
    stmt_3 = MagicMock(st.Statement)
    default_test_case._statements.extend([stmt_1, stmt_2, stmt_3])
    assert not default_test_case.has_statement(-1)
    assert default_test_case.has_statement(1)
    assert not default_test_case.has_statement(3)


def test_hash(default_test_case):
    assert default_test_case.__hash__()


@pytest.mark.parametrize(
    "test_case,other,result",
    [
        pytest.param(get_default_test_case(), None, False),
        pytest.param(get_default_test_case(), "Foo", False),
    ],
)
def test_eq_parameterized(test_case, other, result):
    assert test_case.__eq__(other) == result


def test_eq_same(default_test_case):
    assert default_test_case.__eq__(default_test_case)


def test_eq_statements_1(default_test_case):
    other = dtc.DefaultTestCase()
    other._statements = [MagicMock(st.Statement)]
    assert not default_test_case.__eq__(other)


def test_eq_statements_2(default_test_case):
    default_test_case._statements = [MagicMock(st.Statement)]
    other = dtc.DefaultTestCase()
    other._statements = [MagicMock(st.Statement), MagicMock(st.Statement)]
    assert not default_test_case.__eq__(other)


def test_eq_statements_3(default_test_case):
    default_test_case._statements = [MagicMock(st.Statement)]
    other = dtc.DefaultTestCase()
    other._statements = [MagicMock(st.Statement)]
    assert not default_test_case.__eq__(other)


def test_eq_statements_4(default_test_case):
    statements = [MagicMock(st.Statement), MagicMock(st.Statement)]
    default_test_case._statements = statements
    other = dtc.DefaultTestCase()
    other._statements = statements
    assert default_test_case.__eq__(other)


def test_eq_statements_5(default_test_case):
    default_test_case._statements = []
    other = dtc.DefaultTestCase()
    other._statements = []
    assert default_test_case.__eq__(other)


def test_clone(default_test_case):
    stmt = MagicMock(st.Statement)
    ref = MagicMock(vr.VariableReference)
    stmt.clone.return_value = stmt
    stmt.return_value.clone.return_value = ref
    default_test_case._statements = [stmt]
    result = default_test_case.clone()
    assert isinstance(result, dtc.DefaultTestCase)
    assert result.id != default_test_case.id
    assert result.size() == 1
    assert result.get_statement(0) == stmt


def test_statements(default_test_case):
    assert default_test_case.statements == []


def test_append_test_case(default_test_case):
    stmt = MagicMock(st.Statement)
    stmt.clone.return_value = stmt
    other = dtc.DefaultTestCase()
    other._statements = [stmt]
    assert len(default_test_case.statements) == 0
    default_test_case.append_test_case(other)
    assert len(default_test_case.statements) == 1


def test_get_objects(default_test_case):
    stmt_1 = MagicMock(st.Statement)
    vri_1 = vri.VariableReferenceImpl(default_test_case, int)
    stmt_1.return_value = vri_1
    stmt_2 = MagicMock(st.Statement)
    vri_2 = vri.VariableReferenceImpl(default_test_case, float)
    stmt_2.return_value = vri_2
    stmt_3 = MagicMock(st.Statement)
    vri_3 = vri.VariableReferenceImpl(default_test_case, int)
    stmt_3.return_value = vri_3
    default_test_case._statements = [stmt_1, stmt_2, stmt_3]
    result = default_test_case.get_objects(int, 2)
    assert result == [vri_1]


def test_get_objects_without_type(default_test_case):
    result = default_test_case.get_objects(None, 42)
    assert result == []


def test_set_statement_empty(default_test_case):
    with pytest.raises(AssertionError):
        default_test_case.set_statement(MagicMock(st.Statement), 0)


def test_set_statement_valid(default_test_case):
    int0 = prim.IntPrimitiveStatement(default_test_case, 5)
    int1 = prim.IntPrimitiveStatement(default_test_case, 5)
    default_test_case.add_statement(int0)
    default_test_case.add_statement(int1)
    assert default_test_case.set_statement(int1, 0) == int1.return_value
    assert default_test_case.get_statement(0) == int1


def test_has_changed_default(default_test_case):
    assert default_test_case.has_changed()


@pytest.mark.parametrize("value", [pytest.param(True), pytest.param(False)])
def test_has_changed(default_test_case, value):
    default_test_case.set_changed(value)
    assert default_test_case.has_changed() == value


def test_get_last_execution_last_result_default(default_test_case):
    assert default_test_case.get_last_execution_result() is None


def test_set_last_execution_result(default_test_case):
    result = MagicMock(ExecutionResult)
    default_test_case.set_last_execution_result(result)
    assert default_test_case.get_last_execution_result() == result


def test_get_last_mutatable_statement_empty(default_test_case):
    assert default_test_case._get_last_mutatable_statement() is None


def test_get_last_mutatable_statement_max(default_test_case):
    default_test_case.add_statement(prim.IntPrimitiveStatement(default_test_case, 5))
    assert default_test_case._get_last_mutatable_statement() == 0


def test_get_last_mutatable_statement_mid(default_test_case):
    default_test_case.add_statement(prim.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(prim.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(prim.IntPrimitiveStatement(default_test_case, 5))
    result = MagicMock(ExecutionResult)
    result.has_test_exceptions.return_value = True
    result.get_first_position_of_thrown_exception.return_value = 1
    default_test_case.set_last_execution_result(result)
    assert default_test_case._get_last_mutatable_statement() == 1


def test_get_last_mutatable_statement_too_large(default_test_case):
    default_test_case.add_statement(prim.IntPrimitiveStatement(default_test_case, 5))
    default_test_case.add_statement(prim.IntPrimitiveStatement(default_test_case, 5))
    result = MagicMock(ExecutionResult)
    result.has_test_exceptions.return_value = True
    result.get_first_position_of_thrown_exception.return_value = 4
    default_test_case.set_last_execution_result(result)
    assert (
        default_test_case._get_last_mutatable_statement()
        == default_test_case.size() - 1
    )


def test_mutation_insert_none(default_test_case):
    config.INSTANCE.statement_insertion_probability = 0.0
    assert not default_test_case._mutation_insert()


def test_mutation_insert_two():
    test_factory = MagicMock(tf.TestFactory)

    def side_effect(tc, pos):
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5))
        return 0

    test_factory.insert_random_statement.side_effect = side_effect
    test_case = dtc.DefaultTestCase(test_factory)
    config.INSTANCE.statement_insertion_probability = 0.5
    config.INSTANCE.chromosome_length = 10
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.2, 0.2, 0.2]
        assert test_case._mutation_insert()
    test_factory.insert_random_statement.assert_has_calls(
        [call(test_case, 0), call(test_case, 1)]
    )


def test_mutation_insert_twice_no_success():
    test_factory = MagicMock(tf.TestFactory)

    def side_effect(tc, pos):
        return -1

    test_factory.insert_random_statement.side_effect = side_effect
    test_case = dtc.DefaultTestCase(test_factory)
    config.INSTANCE.statement_insertion_probability = 0.5
    config.INSTANCE.chromosome_length = 10
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.2, 0.2, 0.2]
        assert not test_case._mutation_insert()
    test_factory.insert_random_statement.assert_has_calls(
        [call(test_case, 0), call(test_case, 0)]
    )


def test_mutation_insert_max_length():
    test_factory = MagicMock(tf.TestFactory)

    def side_effect(tc, pos):
        tc.add_statement(prim.IntPrimitiveStatement(tc, 5))
        return 0

    test_factory.insert_random_statement.side_effect = side_effect
    test_case = dtc.DefaultTestCase(test_factory)
    config.INSTANCE.statement_insertion_probability = 0.5
    config.INSTANCE.chromosome_length = 1
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.0, 0.0]
        assert test_case._mutation_insert()
    test_factory.insert_random_statement.assert_has_calls([call(test_case, 0)])
    assert test_case.size() == 1


def test_mutation_change_nothing_to_change(default_test_case):
    assert not default_test_case._mutation_change()


def test_mutation_change_single_prim(default_test_case):
    int0 = prim.IntPrimitiveStatement(default_test_case, 5)
    int0.return_value.distance = 5
    default_test_case.add_statement(int0)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.0]
        assert default_test_case._mutation_change()
        assert int0.return_value.distance == 5


@pytest.mark.parametrize("result", [pytest.param(True), pytest.param(False)])
def test_mutation_change_call_success(constructor_mock, result):
    factory = MagicMock(tf.TestFactory)
    factory.change_random_call.return_value = result
    test_case = dtc.DefaultTestCase(factory)
    const0 = ps.ConstructorStatement(test_case, constructor_mock)
    const0.return_value.distance = 5
    test_case.add_statement(const0)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(const0, "mutate") as mutate_mock:
            mutate_mock.return_value = False
            assert test_case._mutation_change() == result
            mutate_mock.assert_called_once()
            assert const0.return_value.distance == 5


def test_mutation_change_no_change(default_test_case):
    default_test_case.add_statement(prim.IntPrimitiveStatement(default_test_case, 5))
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 1.0
        assert not default_test_case._mutation_change()


@pytest.mark.parametrize("result", [pytest.param(True), pytest.param(False)])
def test_delete_statement(result):
    test_factory = MagicMock(tf.TestFactory)
    test_factory.delete_statement_gracefully.return_value = result
    test_case = dtc.DefaultTestCase(test_factory)
    test_case.add_statement(prim.IntPrimitiveStatement(test_case, 5))
    assert test_case._delete_statement(0) == result
    test_factory.delete_statement_gracefully.assert_called_with(test_case, 0)


def test_mutation_delete_empty(default_test_case):
    assert not default_test_case._mutation_delete()


def test_mutation_delete_not_empty():
    test_case = dtc.DefaultTestCase()
    int0 = prim.IntPrimitiveStatement(test_case, 5)
    int1 = prim.IntPrimitiveStatement(test_case, 5)
    test_case.add_statement(int0)
    test_case.add_statement(int1)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [0.0, 1.0]
        with mock.patch.object(test_case, "_delete_statement") as delete_mock:
            delete_mock.return_value = True
            assert test_case._mutation_delete()
            delete_mock.assert_has_calls([call(1)])
            assert delete_mock.call_count == 1


def test_mutation_delete_skipping():
    test_case = dtc.DefaultTestCase()
    with mock.patch.object(test_case, "_delete_statement") as delete_mock:
        delete_mock.return_value = True
        with mock.patch.object(test_case, "_get_last_mutatable_statement") as mut_mock:
            mut_mock.return_value = 3
            assert not test_case._mutation_delete()
            assert delete_mock.call_count == 0


def test_mutate_chop(default_test_case):
    default_test_case.set_changed(False)
    for i in range(50):
        default_test_case.add_statement(
            prim.IntPrimitiveStatement(default_test_case, 5)
        )
    config.INSTANCE.test_insert_probability = 0.0
    config.INSTANCE.test_change_probability = 0.0
    config.INSTANCE.test_delete_probability = 0.0
    with mock.patch.object(
        default_test_case, "_get_last_mutatable_statement"
    ) as mut_mock:
        mut_mock.return_value = 5
        default_test_case.mutate()
        assert default_test_case.has_changed()
        assert len(default_test_case.statements) == 6


def test_mutate_no_chop(default_test_case):
    for i in range(50):
        default_test_case.add_statement(
            prim.IntPrimitiveStatement(default_test_case, 5)
        )
    default_test_case.set_changed(False)
    config.INSTANCE.test_insert_probability = 0.0
    config.INSTANCE.test_change_probability = 0.0
    config.INSTANCE.test_delete_probability = 0.0
    with mock.patch.object(
        default_test_case, "_get_last_mutatable_statement"
    ) as mut_mock:
        mut_mock.return_value = None
        default_test_case.mutate()
        assert len(default_test_case.statements) == 50
        assert not default_test_case.has_changed()


@pytest.mark.parametrize(
    "func,rand,result",
    [
        pytest.param("_mutation_delete", [0, 1, 1], True),
        pytest.param("_mutation_delete", [0, 1, 1], False),
        pytest.param("_mutation_change", [1, 0, 1], True),
        pytest.param("_mutation_change", [1, 0, 1], False),
        pytest.param("_mutation_insert", [1, 1, 0], True),
        pytest.param("_mutation_insert", [1, 1, 0], False),
    ],
)
def test_mutate_all(default_test_case, func, rand, result):
    default_test_case.set_changed(False)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = rand
        with mock.patch.object(default_test_case, func) as mock_func:
            mock_func.return_value = result
            default_test_case.mutate()
            assert default_test_case.has_changed() == result
            mock_func.assert_called_once()


def test_get_dependencies_self_empty(default_test_case, constructor_mock):
    const0 = ps.ConstructorStatement(default_test_case, constructor_mock)
    default_test_case.add_statement(const0)
    dependencies = default_test_case.get_dependencies(const0.return_value)
    assert dependencies == {const0.return_value}


def test_get_dependencies_chained(default_test_case, function_mock):
    unused_float = prim.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(unused_float)

    float0 = prim.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float0)

    func0 = ps.FunctionStatement(
        default_test_case, function_mock, [float0.return_value]
    )
    default_test_case.add_statement(func0)

    func1 = ps.FunctionStatement(default_test_case, function_mock, [func0.return_value])
    default_test_case.add_statement(func1)
    dependencies = default_test_case.get_dependencies(func1.return_value)
    assert dependencies == {float0.return_value, func0.return_value, func1.return_value}


def test_get_assertions_empty(default_test_case):
    assert default_test_case.get_assertions() == []


@pytest.fixture()
def default_test_case_with_assertions(default_test_case):
    float0 = prim.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float0)
    float0ass0 = pas.PrimitiveAssertion(float0.return_value, 5.5)
    float0ass1 = pas.PrimitiveAssertion(float0.return_value, 6)
    float0.add_assertion(float0ass0)
    float0.add_assertion(float0ass1)

    float1 = prim.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float1)

    float2 = prim.FloatPrimitiveStatement(default_test_case, 5.5)
    default_test_case.add_statement(float2)
    float2ass0 = pas.PrimitiveAssertion(float2.return_value, 5.5)
    float2.add_assertion(float2ass0)
    return default_test_case, {float0ass0, float0ass1, float2ass0}


def test_get_assertions_multiple_statements(default_test_case_with_assertions):
    test_case, assertions = default_test_case_with_assertions
    assert set(test_case.get_assertions()) == assertions


def test_get_size_with_assertions(default_test_case_with_assertions):
    test_case, assertions = default_test_case_with_assertions
    assert test_case.size_with_assertions() == 6  # 3 stmts + 3 assertions
