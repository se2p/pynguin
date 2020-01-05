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

import importlib
import pytest
from unittest.mock import Mock, call
from pynguin.generation.algorithms.wspy.branch_instrumentation import (
    BranchInstrumentation,
)


@pytest.fixture()
def simple_module():
    simple = importlib.import_module("tests.fixtures.instrumentation.simple")
    simple = importlib.reload(simple)
    return simple


def test_entered_method(simple_module):
    tracer = Mock()
    instr = BranchInstrumentation(tracer)
    instr.instrument_method(simple_module.simple_method)
    simple_module.simple_method(1)
    tracer.method_exists.assert_called_once()
    tracer.entered_method.assert_called_once()


def test_add_bool_predicate(simple_module):
    tracer = Mock()
    instr = BranchInstrumentation(tracer)
    instr.instrument_method(simple_module.bool_predicate)
    simple_module.bool_predicate(True)
    tracer.predicate_exists.assert_called_once()
    tracer.passed_bool_predicate.assert_called_once()


def test_add_cmp_predicate(simple_module):
    tracer = Mock()
    instr = BranchInstrumentation(tracer)
    instr.instrument_method(simple_module.cmp_predicate)
    simple_module.cmp_predicate(1, 2)
    tracer.predicate_exists.assert_called_once()
    tracer.passed_cmp_predicate.assert_called_once()


def test_module_instrumentation():
    mixed = importlib.import_module("tests.fixtures.instrumentation.mixed")
    mixed = importlib.reload(mixed)
    tracer = Mock()
    instr = BranchInstrumentation(tracer)
    instr.instrument(mixed)

    inst = mixed.TestClass(5)
    inst.foo()
    mixed.module_function()

    tracer.method_exists.assert_has_calls([call(0), call(1), call(2)])
    tracer.entered_method.assert_has_calls([call(0), call(1), call(2)])
