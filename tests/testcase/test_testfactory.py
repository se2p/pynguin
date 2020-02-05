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
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.fieldstatement as f_stmt
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testfactory as tf
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils.exceptions import ConstructionFailedException
from tests.fixtures.examples.monkey import Monkey


@pytest.mark.parametrize(
    "statement",
    [
        # pytest.param(MagicMock(par_stmt.ConstructorStatement)),
        # pytest.param(MagicMock(par_stmt.MethodStatement)),
        # pytest.param(MagicMock(par_stmt.FunctionStatement)),
        pytest.param(MagicMock(f_stmt.FieldStatement)),
        pytest.param(MagicMock(prim.PrimitiveStatement)),
    ],
)
def test_append_statement(test_case_mock, statement):
    tf.append_statement(test_case_mock, statement)
    test_case_mock.add_statement.assert_called_once()


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
    assert test_case.size() == 4
