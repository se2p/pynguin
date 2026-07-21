#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Characterization tests to pin exact LLM prompt messages/structures."""

from unittest.mock import MagicMock

from pynguin.large_language_model.prompts.assertiongenerationprompt import AssertionGenerationPrompt
from pynguin.large_language_model.prompts.localsearchprompt import LocalSearchPrompt
from pynguin.large_language_model.prompts.testcasegenerationprompt import TestCaseGenerationPrompt
from pynguin.large_language_model.prompts.type_and_subtype_inference_prompt import (
    TypeAndSubtypeInferencePrompt,
)
from pynguin.large_language_model.prompts.typeinferenceprompt import TypeInferencePrompt
from pynguin.large_language_model.prompts.uncoveredtargetsprompt import UncoveredTargetsPrompt
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.report import CoverageEntry, LineAnnotation


class DummyClassForInference:
    def dummy_method(self, x: int) -> str:
        """Dummy docstring."""
        return str(x)


def dummy_function(a: str, b: float):
    """Function docstring."""
    return f"{a} {b}"


def test_test_case_generation_prompt_characterization():
    prompt = TestCaseGenerationPrompt("def foo():\n    pass", "example/path.py")
    assert prompt.system_message == (
        "You are a unit test generating AI (codename TestGenAI). "
        "TestGenAI generates "
        "unit tests for a Python module, just like a senior test "
        "automation engineer "
        "with an ISTQB certificate would. TestGenAI achieves very "
        "high coverage "
        "by boundary value analysis, considering corner cases, "
        "a range of input "
        "values, and relevant combinations."
    )
    user_prompt = prompt.build_prompt()
    expected = (
        "Write unit tests for the following module. Don't use unittest, but only pytest.\n"
        "Module path: `example/path.py`\n"
        "Module source code: `def foo():\n    pass`"
    )
    assert user_prompt == expected


def test_assertion_generation_prompt_characterization():
    prompt = AssertionGenerationPrompt("def test_foo():\n    assert True", "def foo():\n    pass")
    user_prompt = prompt.build_prompt()
    expected = (
        "Write assertions for the following test case:\n"
        "`def test_foo():\n    assert True`\n"
        " ### Add assertions below ###\n\n"
        "Module source code: `def foo():\n    pass`"
    )
    assert user_prompt == expected


def test_uncovered_targets_prompt_characterization():
    func_gao = MagicMock(spec=GenericFunction)
    func_gao.is_method.return_value = False
    func_gao.is_function.return_value = True
    func_gao.is_constructor.return_value = False
    func_gao.function_name = "dummy_func"
    func_gao.inferred_signature = "(a: str) -> None"

    method_gao = MagicMock(spec=GenericMethod)
    method_gao.is_method.return_value = True
    method_gao.is_function.return_value = False
    method_gao.is_constructor.return_value = False
    method_gao.method_name = "dummy_meth"
    method_gao.owner.name = "DummyClass"
    method_gao.inferred_signature = "(self, x: int) -> bool"

    constructor_gao = MagicMock(spec=GenericConstructor)
    constructor_gao.is_method.return_value = False
    constructor_gao.is_function.return_value = False
    constructor_gao.is_constructor.return_value = True
    constructor_gao.owner.name = "DummyClass"
    constructor_gao.inferred_signature = "(self)"

    callables = [func_gao, method_gao, constructor_gao]
    prompt = UncoveredTargetsPrompt(callables, "def source():\n    pass", "dummy/module.py")
    user_prompt = prompt.build_prompt()

    assert (
        "Write unit tests for the following callables that  Pynguin failed to cover:" in user_prompt
    )
    assert "- The function dummy_func(a: str) -> None" in user_prompt
    assert "- The method dummy_meth of class DummyClass(self, x: int) -> bool" in user_prompt
    assert "- The constructor of the class DummyClass(self)" in user_prompt
    assert "Module path: `dummy/module.py`" in user_prompt
    assert "Module source code: `def source():\n    pass`" in user_prompt


def test_local_search_prompt_characterization():
    branch_coverage = [
        LineAnnotation(
            line_no=10,
            total=CoverageEntry(covered=1, existing=2),
            branches=CoverageEntry(covered=1, existing=2),
            branchless_code_objects=CoverageEntry(covered=0, existing=0),
            lines=CoverageEntry(covered=0, existing=0),
        ),
        LineAnnotation(
            line_no=15,
            total=CoverageEntry(covered=0, existing=2),
            branches=CoverageEntry(covered=0, existing=2),
            branchless_code_objects=CoverageEntry(covered=0, existing=0),
            lines=CoverageEntry(covered=0, existing=0),
        ),
    ]
    prompt = LocalSearchPrompt(
        test_case_code="def test_foo():\n    assert True",
        position=2,
        module_code="def foo(x):\n    if x > 0:\n        return 1\n    return 2",
        branch_coverage=branch_coverage,
    )
    user_prompt = prompt.build_prompt()

    # The statement position in local search prompt adds 2 to the position passed.
    assert "Mutate the statement at position 4" in user_prompt
    assert "Line of branches we failed to cover:" in user_prompt
    assert "Line 10: Covered 1 of 2" in user_prompt
    # Line 15 is not included because covered is 0 (branch_coverage filter covered > 0)
    assert "Line 15:" not in user_prompt
    assert "Test case source code:\n `1: def test_foo():\n2:     assert True`" in user_prompt
    assert (
        "Module source code:\n `def foo(x):\n    if x > 0:\n        return 1\n    return 2`"
        in user_prompt
    )


def test_type_inference_prompt_characterization():
    subtypes = OrderedSet(["email", "url"])
    prompt = TypeInferencePrompt(dummy_function, subtypes=subtypes)
    user_prompt = prompt.build_user_prompt()

    assert (
        "You are tasked with inferring parameter types for a given Python function." in user_prompt
    )
    assert "Known string subtypes:\nemail, url" in user_prompt
    assert "Function signature:\n(a: str, b: float)" in user_prompt
    assert "Docstring:\nFunction docstring." in user_prompt
    assert "Function body:\ndef dummy_function(a: str, b: float):" in user_prompt


def test_type_and_subtype_inference_prompt_characterization():
    subtypes = OrderedSet(["email", "url"])
    prompt = TypeAndSubtypeInferencePrompt(dummy_function, subtypes=subtypes)
    user_prompt = prompt.build_user_prompt()

    assert (
        "You are tasked with inferring parameter types and string subtypes for a given Python"
        in user_prompt
    )
    assert "Known string subtypes:\nemail, url" in user_prompt
    assert "Function signature:\n(a: str, b: float)" in user_prompt
    assert "Docstring:\nFunction docstring." in user_prompt
    assert "Function body:\ndef dummy_function(a: str, b: float):" in user_prompt
