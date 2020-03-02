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
import inspect
from inspect import Signature, Parameter
from typing import Union
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.fieldstatement as f_stmt
import pynguin.testcase.statements.parametrizedstatements as par_stmt
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testfactory as tf
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.testfactory import _TestFactory
from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.exceptions import ConstructionFailedException
from tests.fixtures.examples.monkey import Monkey


def test_append_statement_unknown_type(test_case_mock):
    with pytest.raises(ConstructionFailedException):
        tf.append_statement(test_case_mock, MagicMock(Monkey))


@pytest.mark.parametrize(
    "method",
    [
        pytest.param("add_constructor"),
        pytest.param("add_method"),
        pytest.param("add_function"),
        pytest.param("add_field"),
    ],
)
def test_check_recursion_depth_guard(test_case_mock, reset_configuration, method):
    with pytest.raises(ConstructionFailedException):
        getattr(tf, method)(
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
def test_append_statement(test_case_mock, reset_configuration, statement):
    called = False

    def mock(t, s, position=0, allow_none=True):
        nonlocal called
        called = True

    factory = _TestFactory()
    factory.add_constructor = mock
    factory.add_method = mock
    factory.add_function = mock
    factory.add_field = mock
    factory.add_primitive = mock
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
def test_append_generic_statement(test_case_mock, reset_configuration, statement):
    called = False

    def mock(t, s, position=0, allow_none=True, recursion_depth=11):
        nonlocal called
        called = True
        return None

    factory = _TestFactory()
    factory.add_constructor = mock
    factory.add_method = mock
    factory.add_function = mock
    factory.add_field = mock
    factory.add_primitive = mock
    result = factory.append_generic_statement(test_case_mock, statement)
    assert result is None
    assert called


def test_append_illegal_generic_statement(test_case_mock, reset_configuration):
    factory = _TestFactory()
    with pytest.raises(ConstructionFailedException):
        factory.append_generic_statement(
            test_case_mock, MagicMock(prim.PrimitiveStatement), position=42
        )


def test_add_primitive(test_case_mock):
    statement = MagicMock(prim.PrimitiveStatement)
    statement.clone.return_value = statement
    tf.add_primitive(test_case_mock, statement)
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
    result = tf.add_constructor(test_case, generic_constructor, position=0)
    assert result.variable_type == provide_callables_from_fixtures_modules["Basket"]
    assert test_case.size() == 2


def test_add_method(provide_callables_from_fixtures_modules):
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
    result = tf.add_method(test_case, generic_method, position=0)
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
    result = tf.add_function(test_case, generic_function, position=0)
    assert isinstance(result.variable_type, type(None))
    assert test_case.size() <= 4


def test_singleton():
    factory_1 = _TestFactory()
    factory_2 = _TestFactory()
    assert factory_1 is factory_2


@pytest.mark.parametrize(
    "type_, result",
    [
        pytest.param(None, [None]),
        pytest.param(bool, [bool]),
        pytest.param(Union[int, float], (int, float)),
    ],
)
def test_select_from_union(type_, result):
    factory = _TestFactory()
    res = factory._select_from_union(type_)
    assert res in result


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
    factory = _TestFactory()
    result = factory._create_primitive(
        dtc.DefaultTestCase(), type_, position=0, recursion_depth=0,
    )
    assert result.variable_type == statement_type


def test_attempt_generation_for_type(test_case_mock):
    def mock(t, g, position, recursion_depth, allow_none):
        assert position == 0
        assert recursion_depth == 1
        assert allow_none

    factory = _TestFactory()
    factory.append_generic_statement = mock
    factory._attempt_generation_for_type(
        test_case_mock, 0, 0, True, {MagicMock(gao.GenericAccessibleObject)}
    )


def test_attempt_generation_for_no_type(test_case_mock):
    factory = _TestFactory()
    result = factory._attempt_generation(test_case_mock, None, 0, 0, True)
    assert result is None


def test_attempt_generation_for_none_type(reset_configuration):
    config.INSTANCE.none_probability = 1.0
    factory = _TestFactory()
    result = factory._attempt_generation(
        dtc.DefaultTestCase(), MagicMock(_TestFactory), 0, 0, True
    )
    assert result.distance == 0


def test_attempt_generation_for_none_type_with_no_probability(reset_configuration):
    config.INSTANCE.none_probability = 0.0
    factory = _TestFactory()
    result = factory._attempt_generation(
        dtc.DefaultTestCase(), MagicMock(_TestFactory), 0, 0, True
    )
    assert result is None


def test_attempt_generation_for_type_from_cluster(test_case_mock, reset_configuration):
    def mock(t, position, recursion_depth, allow_none, type_generators):
        assert position == 0
        assert recursion_depth == 0
        assert allow_none
        assert isinstance(type_generators, gao.GenericAccessibleObject)

    cluster = TestCluster()
    cluster.get_generators_for = lambda t: MagicMock(gao.GenericAccessibleObject)
    factory = _TestFactory()
    factory._attempt_generation_for_type = mock
    factory._attempt_generation(test_case_mock, MagicMock(_TestFactory), 0, 0, True)
