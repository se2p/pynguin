#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from _ast import Module
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
        astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var_0 is None\n"
    )


def test_not_none(assertion_to_ast):
    assertion = MagicMock(value=False)
    assertion_to_ast.visit_none_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes))
        == "assert var_0 is not None\n"
    )


def test_primitive_bool(assertion_to_ast):
    assertion = MagicMock(value=True)
    assertion_to_ast.visit_primitive_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var_0 is True\n"
    )


def test_primitive_float(assertion_to_ast):
    assertion = MagicMock(value=1.5)
    assertion_to_ast.visit_primitive_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes))
        == "assert var_0 == pytest.approx(1.5, abs=0.01, rel=0.01)\n"
    )


def test_primitive_non_bool(assertion_to_ast):
    assertion = MagicMock(value=42)
    assertion_to_ast.visit_primitive_assertion(assertion)
    assert (
        astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var_0 == 42\n"
    )
