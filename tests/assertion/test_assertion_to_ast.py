#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
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
    return ata.AssertionToAstVisitor(scope)


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


def test_primitive_non_bool(assertion_to_ast):
    assertion = MagicMock(value=42)
    assertion_to_ast.visit_primitive_assertion(assertion)
    assert astor.to_source(Module(body=assertion_to_ast.nodes)) == "assert var0 == 42\n"
