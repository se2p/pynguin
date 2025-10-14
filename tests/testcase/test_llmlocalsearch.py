#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from pynguin.large_language_model.prompts.localsearchprompt import LocalSearchPrompt
from pynguin.utils.report import CoverageEntry
from pynguin.utils.report import LineAnnotation


def test_prompt() -> None:
    annotation = LineAnnotation(
        2, CoverageEntry(0, 0), CoverageEntry(1, 2), CoverageEntry(0, 0), CoverageEntry(0, 0)
    )
    line_annotations = [annotation]
    position = 2
    test_case_code = "def test_module:\n    number = 3\n    object = TestClass(number)"
    source_code = (
        "class TestClass\n    def __init__(self, number:int):\n       self.number = number\n"
    )
    local_search_prompt = LocalSearchPrompt(test_case_code, position, source_code, line_annotations)
    result = local_search_prompt.build_prompt()
    prompt = (
        "Mutate the statement at position 4 of the test case to achieve higher branch "
        "coverage\n"
        "Give back only the whole test and not the variable itself as Python code for "
        "better parsing\n"
        "Also add a class where the test is in to the test_code.\n"
        "Pick a branch where mutating the provided statement can actually increase "
        "the branch coverage.\n"
        " Line of branches we failed to cover:\n"
        "Line 2: Covered 1 of 2\n"
        "Test case source code:\n"
        " `1: def test_module:\n"
        "2:     number = 3\n"
        "3:     object = TestClass(number)` \n"
        "Module source code:\n"
        " `class TestClass\n"
        "    def __init__(self, number:int):\n"
        "       self.number = number\n"
        "`"
    )
    assert result == str(prompt)


def test_build_uncovered_branches_empty() -> None:
    line_annotations = []
    local_search_prompt = LocalSearchPrompt("", 0, "", line_annotations)
    assert local_search_prompt.build_uncovered_branch_section() == []


def test_build_uncovered_branches() -> None:
    annotation = LineAnnotation(
        2, CoverageEntry(0, 0), CoverageEntry(1, 2), CoverageEntry(0, 0), CoverageEntry(0, 0)
    )
    annotation2 = LineAnnotation(
        2, CoverageEntry(0, 0), CoverageEntry(0, 0), CoverageEntry(0, 0), CoverageEntry(0, 0)
    )
    line_annotations = [annotation, annotation2]
    local_search_prompt = LocalSearchPrompt("", 0, "", line_annotations)
    assert local_search_prompt.build_uncovered_branch_section() == ["Line 2: Covered 1 of 2"]


def test_build_uncovered_branches2() -> None:
    annotation = LineAnnotation(
        2, CoverageEntry(0, 0), CoverageEntry(1, 2), CoverageEntry(0, 0), CoverageEntry(0, 0)
    )
    annotation2 = LineAnnotation(
        5, CoverageEntry(0, 0), CoverageEntry(3, 4), CoverageEntry(0, 0), CoverageEntry(0, 0)
    )
    line_annotations = [annotation, annotation2]
    local_search_prompt = LocalSearchPrompt("", 0, "", line_annotations)
    assert local_search_prompt.build_uncovered_branch_section() == [
        "Line 2: Covered 1 of 2",
        "Line 5: Covered 3 of 4",
    ]
