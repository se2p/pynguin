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
import sys
from typing import Callable
from unittest import mock
from unittest.mock import MagicMock

import pytest
from coverage import Coverage

from pynguin.generation.executor import Executor
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.proxy import MagicProxy
from pynguin.utils.statements import (
    Sequence,
    Call,
    Expression,
    Assignment,
    Name,
    Attribute,
)


class _Dummy:
    _hasError = False

    def baz(self, a, b):
        return a + b if not self._hasError else -1


def _dummy():
    return 42


def test_accumulated_coverage():
    executor = Executor([])
    coverage = executor.accumulated_coverage
    assert isinstance(coverage, Coverage)


def test_load_modules():
    executor = Executor([])
    executor.load_modules()


def test_execute():
    executor = Executor([])
    executor.execute(MagicMock(Sequence))


def test__reset_error_flags():
    sequence = Sequence()
    arg_1 = object()
    arg_2 = _Dummy()
    arg_2._hasError = True
    arg_3 = _Dummy()
    arg_3._hasError = True
    call_1 = Call(function=MagicMock(Expression), arguments=[arg_1, arg_2])
    call_2 = Call(function=MagicMock(Expression), arguments=[arg_1, arg_3])
    assignment_1 = Assignment(lhs=MagicMock(Expression), rhs=call_2)
    assignment_2 = Assignment(lhs=MagicMock(Expression), rhs=MagicMock(Expression))
    sequence.append(call_1)
    sequence.append(assignment_1)
    sequence.append(assignment_2)

    Executor._reset_error_flags(sequence)

    assert not arg_2._hasError
    assert not arg_3._hasError


def test__get_call_wrapper_without_arguments():
    def dummy():
        return 42

    result = Executor._get_call_wrapper(dummy, [])
    assert result() == 42


def test__get_call_wrapper_with_arguments():
    def dummy(a, b):
        return a + b

    result = Executor._get_call_wrapper(dummy, [23, 42])
    assert result() == 65


def test__get_ref_label_equals_name():
    values = {"bar": 23, "foo": 42}
    result = Executor._get_ref("foo", values, [])
    assert result == 42


def test__get_ref_class_type_equals_name():
    classes = [_Dummy]
    result = Executor._get_ref("_Dummy", {}, classes)
    assert result == _Dummy


def test__get_ref():
    Executor._get_ref("foo", {}, [])


def test__get_ref_class_type_in_name():
    classes = [_Dummy]
    with mock.patch("pynguin.generation.executor.inspect.getmembers") as m:
        m.return_value = {"foo.bar._Dummy": 42}.items()
        result = Executor._get_ref("foo.bar._Dummy", {}, classes)
        assert result == 42


def test__get_ref_class_type_in_name_no_match():
    classes = [_Dummy]
    with mock.patch("pynguin.generation.executor.inspect.getmembers") as m:
        m.return_value = {"foo.baz._Dummy": 42}.items()
        Executor._get_ref("foo.bar._Dummy", {}, classes)


def test__get_ref_class_type_not_equals_name():
    classes = [_Dummy]
    Executor._get_ref("String", {}, classes)


def test__get_argument_list_no_statements():
    executor = Executor([])
    assert executor._get_argument_list([], {}, []) == []


def test__get_argument_list_string():
    executor = Executor([])
    result = executor._get_argument_list(["foo"], {}, [])
    assert result == ["foo"]


def test__get_argument_list_name():
    executor = Executor([])
    result = executor._get_argument_list(
        [Name(identifier="_Dummy")], {"_Dummy": 42}, [_Dummy]
    )
    assert result == [42]


def test__get_argument_list_proxy():
    executor = Executor([])
    arguments = [MagicProxy(Name(identifier="_Dummy"))]
    result = executor._get_argument_list(arguments, {"_Dummy": 42}, [_Dummy])
    assert result == [42]


def test__exec_call_without_call_function():
    executor = Executor([])
    call = Call(function=MagicMock(Expression), arguments=[])
    with pytest.raises(NotImplementedError) as error:
        executor._exec_call(call, {}, [])
    assert "No execution implemented for type" in error.value.args[0]


@pytest.mark.skipif(
    sys.version_info >= (3, 8),
    reason="Errors with recursion depth exceeding on Python 3.8",
)
def test__exec_call_with_name_function():
    executor = Executor([])
    call = Call(function=Name(identifier="_dummy"), arguments=[])
    with mock.patch("pynguin.generation.executor.inspect.signature") as mocking:
        mocking.return_value.parameters.return_value = []
        cbl, inputs = executor._exec_call(call, {"_dummy": 42}, [])
        assert inputs == {}
        assert isinstance(cbl, Callable)


def test__exec_call_with_incomplete_attribute():
    executor = Executor([])
    call = Call(
        function=Attribute(owner=Name(identifier=None), attribute_name=""), arguments=[]
    )
    with pytest.raises(GenerationException) as exception:
        executor._exec_call(call, {}, [])
    assert "Cannot call methods on None" == exception.value.args[0]


@pytest.mark.skipif(
    sys.version_info >= (3, 8),
    reason="Errors with recursion depth exceeding on Python 3.8",
)
def test__exec_call_with_attribute():
    executor = Executor([])
    call = Call(
        function=Attribute(owner=Name(identifier="_Dummy"), attribute_name="baz"),
        arguments=[int, int],
    )
    with mock.patch("pynguin.generation.executor.inspect.signature") as mocking:
        mocking.return_value.parameters.return_value = [int, int]
        cbl, inputs = executor._exec_call(call, {"a": 42, "b": 23}, [_Dummy])
        assert inputs == {}
        assert isinstance(cbl, Callable)


def test__get_arcs_for_classes_without_coverage():
    executor = Executor([])
    assert not executor._get_arcs_for_classes([])


@pytest.mark.skip(reason="Does currently not work with Coverage.py v5.0")
def test__get_arcs_for_classes_with_coverage():
    executor = Executor([], measure_coverage=True)
    assert executor._get_arcs_for_classes([_Dummy]) == []
