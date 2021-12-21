#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import enum
from _ast import Module
from unittest.mock import MagicMock

import astor
import pytest

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertion_to_ast as ata
import pynguin.testcase.variablereference as vr
from pynguin.utils.namingscope import NamingScope


@pytest.fixture
def assertion_to_ast() -> ata.AssertionToAstVisitor:
    scope = NamingScope()
    module_aliases = NamingScope(prefix="module")
    return ata.AssertionToAstVisitor(scope, module_aliases, set())


def test_none(assertion_to_ast):
    assertion = ass.NotNoneAssertion(source=vr.VariableReference(MagicMock(), None))
    assertion.accept(assertion_to_ast)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes))
        == "assert var_0 is not None\n"
    )


@pytest.mark.parametrize(
    "obj,output",
    [
        (True, "assert var_0 is True\n"),
        (False, "assert var_0 is False\n"),
        ((True, False), "assert var_0 == (True, False)\n"),
        ([3, 8], "assert var_0 == [3, 8]\n"),
        ([[3, 8], {"foo"}], "assert var_0 == [[3, 8], {'foo'}]\n"),
        (
            {"foo": ["nope", 1, False, None]},
            "assert var_0 == {'foo': ['nope', 1, False, None]}\n",
        ),
        (
            {"foo": "bar", "baz": "argh"},
            "assert var_0 == {'foo': 'bar', 'baz': 'argh'}\n",
        ),
        (
            {enum.Enum("Dummy", "a").a: False},
            "assert var_0 == {module_0.Dummy.a: False}\n",
        ),
    ],
)
def test_object_assertion(assertion_to_ast, obj, output):
    assertion = ass.ObjectAssertion(
        source=vr.VariableReference(MagicMock(), None), value=obj
    )
    assertion.accept(assertion_to_ast)
    assert astor.to_source(Module(body=assertion_to_ast.nodes)) == output


def test_float_assertion(assertion_to_ast):
    assertion = ass.FloatAssertion(
        source=vr.VariableReference(MagicMock(), None), value=1.5
    )
    assertion.accept(assertion_to_ast)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes))
        == "assert var_0 == pytest.approx(1.5, abs=0.01, rel=0.01)\n"
    )


@pytest.mark.parametrize(
    "length, output",
    [(0, "assert len(var_0) == 0\n"), (42, "assert len(var_0) == 42\n")],
)
def test_collection_length(assertion_to_ast, length, output):
    assertion = ass.CollectionLengthAssertion(
        source=vr.VariableReference(MagicMock(), None), length=length
    )
    assertion.accept(assertion_to_ast)
    assert astor.to_source(Module(body=assertion_to_ast.nodes)) == output
