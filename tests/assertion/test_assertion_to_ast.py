#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import astor
import pytest
from _ast import Module

import pynguin.assertion.assertion_to_ast as ata
from pynguin.utils.namingscope import NamingScope


@pytest.fixture
def assertion_to_ast() -> ata.AssertionToAstVisitor:
    scope = NamingScope()
    module_aliases = NamingScope()
    return ata.AssertionToAstVisitor(set(), module_aliases, scope)


@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    yield
    ata.AssertionToAstVisitor._obj_index = 0


def test_none(assertion_to_ast):
    assertion = MagicMock(value=True)
    assertion_to_ast.visit_none_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var0 is None\n"
    )


def test_not_none(assertion_to_ast):
    assertion = MagicMock(value=False)
    assertion_to_ast.visit_none_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes))
        == "assert var0 is not None\n"
    )


def test_primitive_bool(assertion_to_ast):
    assertion = MagicMock(value=True)
    assertion_to_ast.visit_primitive_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var0 is True\n"
    )


def test_primitive_float(assertion_to_ast):
    assertion = MagicMock(value=1.5)
    assertion_to_ast.visit_primitive_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes))
        == "assert var0 == pytest.approx(1.5, abs=0.01, rel=0.01)\n"
    )


def test_primitive_non_bool(assertion_to_ast):
    assertion = MagicMock(value=42)
    assertion_to_ast.visit_primitive_assertion(assertion)
    assert astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var0 == 42\n"


class Foo:
    def __init__(self, bar: str):
        self._bar = bar


def test_complex_object(assertion_to_ast):
    assertion = MagicMock(value=Foo("bar"))
    assertion_to_ast.visit_complex_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    assert (
        astor.to_source(module) == "obj0 = type('', (object,), {})()\n"
        "obj0.__class__ = var0.Foo\n"
        "obj0._bar = 'bar'\n"
        "assert var0 == obj0\n"
    )


def test_complex_primitive(assertion_to_ast):
    assertion = MagicMock(value=42)
    assertion_to_ast.visit_complex_assertion(assertion)
    assert astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var0 == 42\n"


def test_complex_list(assertion_to_ast):
    value = [Foo("foo"), Foo("bar"), 42]
    assertion = MagicMock(value=value)
    assertion_to_ast.visit_complex_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    assert (
        astor.to_source(module) == "obj1 = type('', (object,), {})()\n"
        "obj1.__class__ = var0.Foo\n"
        "obj1._bar = 'foo'\n"
        "obj2 = type('', (object,), {})()\n"
        "obj2.__class__ = var0.Foo\n"
        "obj2._bar = 'bar'\n"
        "obj0 = [obj1, obj2, 42]\n"
        "assert var0 == obj0\n"
    )


def test_complex_set(assertion_to_ast):
    value = {Foo("foo"), Foo("bar"), 42}
    assertion = MagicMock(value=value)
    assertion_to_ast.visit_complex_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    source = astor.to_source(module)
    assert len(source) == 198
    assert source.startswith(
        "obj1 = type('', (object,), {})()\nobj1.__class__ = var0.Foo\nobj1._bar = "
    )
    assert source.endswith("\nassert var0 == obj0\n")


def test_complex_dict(assertion_to_ast):
    value = {Foo("foo"): "foo", "bar": Foo("bar"), 42: 1337}
    assertion = MagicMock(value=value)
    assertion_to_ast.visit_complex_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    assert (
        astor.to_source(module) == "obj1 = type('', (object,), {})()\n"
        "obj1.__class__ = var0.Foo\n"
        "obj1._bar = 'foo'\n"
        "obj2 = type('', (object,), {})()\n"
        "obj2.__class__ = var0.Foo\n"
        "obj2._bar = 'bar'\n"
        "obj0 = {obj1: 'foo', 'bar': obj2, (42): 1337}\n"
        "assert var0 == obj0\n"
    )


def test_complex_tuple(assertion_to_ast):
    value = (Foo("foo"), Foo("bar"), 42)
    assertion = MagicMock(value=value)
    assertion_to_ast.visit_complex_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    assert (
        astor.to_source(module)
        == """obj1 = type('', (object,), {})()
obj1.__class__ = var0.Foo
obj1._bar = 'foo'
obj2 = type('', (object,), {})()
obj2.__class__ = var0.Foo
obj2._bar = 'bar'
obj0 = obj1, obj2, 42
assert var0 == obj0
"""
    )


def test_field_global(assertion_to_ast):
    assertion = MagicMock(value=42, field="foo", module="var0")
    assertion_to_ast.visit_field_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    assert astor.to_source(module) == "assert var0.foo == 42\n"


def test_field_attribute(assertion_to_ast):
    assertion = MagicMock(value=42, field="foo")
    assertion_to_ast.visit_field_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    assert astor.to_source(module) == "assert var0.foo == 42\n"


def test_field_class(assertion_to_ast):
    assertion = MagicMock(value=42, field="foo", owners=["clazz"])
    assertion_to_ast.visit_field_assertion(assertion)
    module = Module(body=assertion_to_ast.nodes)
    assert astor.to_source(module) == "assert var0.clazz.foo == 42\n"
