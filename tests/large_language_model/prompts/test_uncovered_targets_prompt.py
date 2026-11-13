#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

from unittest.mock import MagicMock

import pytest

from pynguin.configuration import ProblemCardType
from pynguin.large_language_model.problem_cards import ProblemCard
from pynguin.large_language_model.prompts.uncoveredtargetsprompt import (
    UncoveredTargetsPrompt,
)
from pynguin.large_language_model.targets import TargetDiagnosis
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)


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

    assert "Pynguin failed to cover the following callables" in result
    assert "- The function foo(a: int) -> str" in result
    assert f"Module path: `{module_info['path']}`" in result
    assert module_info["code"] in result


def test_build_callables_prompt_section_includes_diagnostics(module_info):
    foo = make_generic_function("foo")
    bar = make_generic_method("MyClass", "bar")
    prompt = UncoveredTargetsPrompt(
        [foo, bar],
        module_info["code"],
        module_info["path"],
        diagnostics={
            foo: TargetDiagnosis(
                cards=(
                    ProblemCard(
                        ProblemCardType.UNREACHED_CALLABLE,
                        foo,
                        None,
                        "never reached; construct valid inputs",
                    ),
                ),
                uncovered_lines=(3, 4, 5, 9),
                missing_branches=((2, False),),
            )
        },
    )
    result = prompt.build_callables_prompt_section()

    # foo lists its goals and hint; bar (no diagnosis) only has its header.
    assert result[0] == (
        "- The function foo(a: int) -> str\n"
        "  - Uncovered lines: 3-5, 9\n"
        "  - Branch outcomes never taken: line 2 (False)\n"
        "  - Hint: never reached; construct valid inputs"
    )
    assert result[1] == "- The method bar of class MyClass(self, x: float) -> None"


def test_build_prompt_renders_diagnosis_as_nested_list(module_info):
    foo = make_generic_function("foo")
    prompt = UncoveredTargetsPrompt(
        [foo],
        module_info["code"],
        module_info["path"],
        diagnostics={foo: TargetDiagnosis(uncovered_lines=(7,))},
    )
    result = prompt.build_prompt()

    assert "- The function foo(a: int) -> str\n  - Uncovered lines: 7\n" in result
    assert "aim each test" in result  # the instruction explaining the goal lists


@pytest.mark.parametrize("tests_per_query", [0, 3])
def test_build_prompt_asks_for_tests_per_query(module_info, tests_per_query):
    prompt = UncoveredTargetsPrompt(
        [make_generic_function("foo")],
        module_info["code"],
        module_info["path"],
        tests_per_query=tests_per_query,
    )
    result = prompt.build_prompt()

    if tests_per_query:
        assert f"Write exactly {tests_per_query} test functions." in result
    else:
        assert "Write exactly" not in result


def test_skips_unknown_callable_type(module_info):
    unknown_gao = MagicMock()
    unknown_gao.is_method.return_value = False
    unknown_gao.is_function.return_value = False
    unknown_gao.is_constructor.return_value = False
    prompt = UncoveredTargetsPrompt([unknown_gao], module_info["code"], module_info["path"])

    result = prompt.build_callables_prompt_section()
    assert result == []


def test_build_prompt_clarifies_pytest_raises_usage(module_info):
    callables = [make_generic_function("foo")]
    prompt = UncoveredTargetsPrompt(callables, module_info["code"], module_info["path"])
    result = prompt.build_prompt()

    assert "Only wrap calls in `with pytest.raises(...)`" in result
    assert "suppresses, or logs" in result
    assert "without `pytest.raises`" in result


def test_build_prompt_includes_make_dataclass_instruction(module_info):
    callables = [make_generic_function("foo")]
    prompt = UncoveredTargetsPrompt(callables, module_info["code"], module_info["path"])
    result = prompt.build_prompt()

    assert "make_dataclass" in result
