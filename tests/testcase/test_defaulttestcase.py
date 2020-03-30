# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.statement as st
import pynguin.testcase.statements.primitivestatements as prim
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


def test_failing(default_test_case):
    assert not default_test_case.is_failing()
    default_test_case.set_failing()
    assert default_test_case.is_failing()


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
