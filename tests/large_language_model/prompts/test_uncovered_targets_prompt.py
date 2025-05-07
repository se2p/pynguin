#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

from unittest.mock import MagicMock

import pytest

from pynguin.large_language_model.prompts.uncoveredtargetsprompt import (
    UncoveredTargetsPrompt,
)
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod


@pytest.fixture
def module_info():
    return {
        "code": "def foo(): pass",
        "path": "example/module.py",
    }


def make_generic_function(name="foo"):
    gao = MagicMock(spec=GenericFunction)
    gao.is_method.return_value = False
    gao.is_function.return_value = True
    gao.is_constructor.return_value = False
    gao.function_name = name
    gao.inferred_signature = "(a: int) -> str"
    return gao


def make_generic_method(class_name="MyClass", method_name="bar"):
    gao = MagicMock(spec=GenericMethod)
    gao.is_method.return_value = True
    gao.is_function.return_value = False
    gao.is_constructor.return_value = False
    gao.method_name = method_name
    gao.owner.name = class_name
    gao.inferred_signature = "(self, x: float) -> None"
    return gao


def make_generic_constructor(class_name="MyClass"):
    gao = MagicMock(spec=GenericConstructor)
    gao.is_method.return_value = False
    gao.is_function.return_value = False
    gao.is_constructor.return_value = True
    gao.owner.name = class_name
    gao.inferred_signature = "(self, y: str)"
    return gao


def test_build_callables_prompt_section_all_kinds(module_info):
    callables = [
        make_generic_function("foo"),
        make_generic_method("MyClass", "bar"),
        make_generic_constructor("MyClass"),
    ]

    prompt = UncoveredTargetsPrompt(callables, module_info["code"], module_info["path"])
    result = prompt.build_callables_prompt_section()

    assert "- The function foo(a: int) -> str" in result
    assert "- The method bar of class MyClass(self, x: float) -> None" in result
    assert "- The constructor of the class MyClass(self, y: str)" in result


def test_build_prompt_aggregates_sections(module_info):
    callables = [make_generic_function("foo")]
    prompt = UncoveredTargetsPrompt(callables, module_info["code"], module_info["path"])
    result = prompt.build_prompt()

    assert "Write unit tests for the following callables" in result
    assert "- The function foo(a: int) -> str" in result
    assert f"Module path: `{module_info['path']}`" in result
    assert f"Module source code: `{module_info['code']}`" in result


def test_skips_unknown_callable_type(module_info):
    unknown_gao = MagicMock()
    unknown_gao.is_method.return_value = False
    unknown_gao.is_function.return_value = False
    unknown_gao.is_constructor.return_value = False
    prompt = UncoveredTargetsPrompt([unknown_gao], module_info["code"], module_info["path"])

    result = prompt.build_callables_prompt_section()
    assert result == []
