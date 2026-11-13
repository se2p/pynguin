#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.coveragegoals as bg
from pynguin.configuration import ProblemCardType
from pynguin.instrumentation.tracer import LineMetaData, SubjectProperties
from pynguin.large_language_model import targets
from pynguin.large_language_model.problem_cards import ProblemCard
from pynguin.large_language_model.targets import (
    TargetDiagnosis,
    collect_uncovered_goals,
    describe,
    format_line_numbers,
    source_range,
)


def _line_goal(line_id: int) -> MagicMock:
    fitness = MagicMock()
    fitness.goal = bg.LineCoverageGoal(0, line_id)
    return fitness


def _branch_goal(predicate_id: int, *, value: bool) -> MagicMock:
    fitness = MagicMock()
    fitness.goal = bg.BranchGoal(0, predicate_id, value=value)
    return fitness


@pytest.fixture
def subject_properties() -> SubjectProperties:
    properties = SubjectProperties()
    for line_id, line_number in {0: 3, 1: 4, 2: 5, 3: 12, 4: 30}.items():
        properties.existing_lines[line_id] = LineMetaData(0, "module.py", line_number)
    for predicate_id, line_no in {0: 2, 1: 11}.items():
        predicate = MagicMock()
        predicate.line_no = line_no
        properties.existing_predicates[predicate_id] = predicate
    return properties


def test_collect_uncovered_goals_groups_lines_and_branches_by_callable(subject_properties):
    outer, inner = MagicMock(), MagicMock()
    ranges = {outer: (1, 20), inner: (10, 13)}
    goals = [
        _line_goal(1),
        _line_goal(0),
        _line_goal(2),
        _line_goal(3),
        _line_goal(4),  # line 30: in no callable
        _branch_goal(0, value=False),
        _branch_goal(1, value=True),
        MagicMock(goal=bg.BranchlessCodeObjectGoal(0)),
    ]

    result = collect_uncovered_goals(ranges, goals, subject_properties)

    assert result[outer] == TargetDiagnosis(
        uncovered_lines=(3, 4, 5), missing_branches=((2, False),)
    )
    # Goals inside the nested range belong to the innermost callable only.
    assert result[inner] == TargetDiagnosis(uncovered_lines=(12,), missing_branches=((11, True),))


def test_collect_uncovered_goals_skips_unknown_ids_and_callables_without_goals(
    subject_properties,
):
    covered = MagicMock()
    result = collect_uncovered_goals(
        {covered: (1, 20)},
        [_line_goal(99), _branch_goal(99, value=True)],
        subject_properties,
    )
    assert result == {}


def test_collect_uncovered_goals_caps_the_number_of_goals(monkeypatch, subject_properties):
    monkeypatch.setattr(targets, "MAX_GOALS_PER_TARGET", 2)
    gao = MagicMock()
    goals = [_line_goal(0), _line_goal(1), _line_goal(2), _branch_goal(0, value=True)]

    result = collect_uncovered_goals({gao: (1, 20)}, goals, subject_properties)

    # Branch outcomes are kept before lines.
    assert result[gao] == TargetDiagnosis(
        uncovered_lines=(3,), missing_branches=((2, True),), omitted_goals=2
    )


@pytest.mark.parametrize(
    "lines,expected",
    [
        ((), ""),
        ((4,), "4"),
        ((3, 7, 8, 9, 12), "3, 7-9, 12"),
        ((1, 2), "1-2"),
    ],
)
def test_format_line_numbers(lines, expected):
    assert format_line_numbers(lines) == expected


def test_describe_lists_goals_then_hints():
    card = ProblemCard(ProblemCardType.UNREACHED_CALLABLE, MagicMock(), None, "never reached")
    diagnosis = TargetDiagnosis(
        cards=(card,),
        uncovered_lines=(3, 4, 9),
        missing_branches=((2, False), (8, True)),
        omitted_goals=5,
    )
    assert describe(diagnosis) == [
        "Uncovered lines: 3-4, 9",
        "Branch outcomes never taken: line 2 (False), line 8 (True)",
        "... and 5 more uncovered goals",
        "Hint: never reached",
    ]


def test_empty_diagnosis_is_falsy():
    assert not TargetDiagnosis()
    assert not TargetDiagnosis(omitted_goals=1)
    assert TargetDiagnosis(
        cards=(ProblemCard(ProblemCardType.UNREACHED_CALLABLE, MagicMock(), None, "x"),)
    )
    assert TargetDiagnosis(missing_branches=((1, True),))


def _sample(value):
    return value


def test_source_range_of_python_function():
    gao = MagicMock()
    gao.callable = _sample
    start, end = source_range(gao)
    assert end == start + 1


def test_source_range_of_builtin_is_none():
    gao = MagicMock()
    gao.callable = len
    assert source_range(gao) is None
