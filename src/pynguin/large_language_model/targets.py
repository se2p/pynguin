# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Goal-level descriptions of the callables an uncovered-targets prompt asks for."""

from __future__ import annotations

import dataclasses
import inspect
from typing import TYPE_CHECKING

from pynguin.ga.coveragegoals import BranchGoal, LineCoverageGoal

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

    import pynguin.ga.computations as ff
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject

# How many uncovered lines and branch outcomes a prompt lists per callable.
MAX_GOALS_PER_TARGET = 20


@dataclasses.dataclass(frozen=True)
class TargetDiagnosis:
    """What a prompt tells the LLM about one uncovered callable.

    Attributes:
        hints: Free-text hints on why the callable is uncovered.
        uncovered_lines: Line numbers of the uncovered line goals, ascending.
        missing_branches: ``(line, outcome)`` pairs of branch outcomes that were never
            taken, ascending.
        omitted_goals: How many further uncovered goals were left out of the two
            lists above to keep the prompt short.
    """

    hints: tuple[str, ...] = ()
    uncovered_lines: tuple[int, ...] = ()
    missing_branches: tuple[tuple[int, bool], ...] = ()
    omitted_goals: int = 0

    def __bool__(self) -> bool:
        """Whether the diagnosis tells the LLM anything.

        Returns:
            ``True`` if it has a hint or lists an uncovered goal.
        """
        return bool(self.hints or self.uncovered_lines or self.missing_branches)


def source_range(gao: GenericCallableAccessibleObject) -> tuple[int, int] | None:
    """The first and last source line of a callable.

    Args:
        gao: The callable.

    Returns:
        The inclusive line range, or ``None`` if the source is not available.
    """
    try:
        source_lines, start_line = inspect.getsourcelines(gao.callable)
    except (TypeError, OSError):
        return None
    return start_line, start_line + len(source_lines) - 1


def _goal_location(
    fitness: ff.FitnessFunction, subject_properties: SubjectProperties
) -> tuple[int, bool | None] | None:
    """The source line of a goal and, for a branch goal, its outcome.

    Args:
        fitness: The fitness function of the goal.
        subject_properties: The properties of the subject under test.

    Returns:
        ``(line, None)`` for a line goal, ``(line, outcome)`` for a branch goal, or
        ``None`` for any other goal or a goal without known location.
    """
    goal = getattr(fitness, "goal", None)
    if isinstance(goal, LineCoverageGoal):
        line_meta = subject_properties.existing_lines.get(goal.line_id)
        return None if line_meta is None else (line_meta.line_number, None)
    if isinstance(goal, BranchGoal):
        predicate_meta = subject_properties.existing_predicates.get(goal.predicate_id)
        return None if predicate_meta is None else (predicate_meta.line_no, goal.value)
    return None


def _innermost(
    ranges: Mapping[GenericCallableAccessibleObject, tuple[int, int]], line: int
) -> GenericCallableAccessibleObject | None:
    """The callable with the smallest source range that contains a line.

    Args:
        ranges: The source range of each callable.
        line: The line number.

    Returns:
        The callable, or ``None`` if no range contains the line.
    """
    best: GenericCallableAccessibleObject | None = None
    best_size = 0
    for gao, (start, end) in ranges.items():
        if start <= line <= end and (best is None or end - start < best_size):
            best, best_size = gao, end - start
    return best


def collect_uncovered_goals(
    ranges: Mapping[GenericCallableAccessibleObject, tuple[int, int]],
    uncovered_goals: Iterable[ff.FitnessFunction],
    subject_properties: SubjectProperties,
) -> dict[GenericCallableAccessibleObject, TargetDiagnosis]:
    """Groups uncovered line and branch goals by the callable that contains them.

    A goal belongs to the innermost callable whose source range contains its line,
    so goals of nested functions, lambdas and comprehensions count for the callable
    they are written in. Each callable lists at most ``MAX_GOALS_PER_TARGET`` goals,
    lines first.

    Args:
        ranges: The source range of each callable.
        uncovered_goals: The goals to group.
        subject_properties: The properties of the subject under test.

    Returns:
        A diagnosis without hints for every callable that has an uncovered goal.
    """
    lines: dict[GenericCallableAccessibleObject, set[int]] = {}
    branches: dict[GenericCallableAccessibleObject, set[tuple[int, bool]]] = {}
    for fitness in uncovered_goals:
        location = _goal_location(fitness, subject_properties)
        if location is None:
            continue
        line, outcome = location
        gao = _innermost(ranges, line)
        if gao is None:
            continue
        if outcome is None:
            lines.setdefault(gao, set()).add(line)
        else:
            branches.setdefault(gao, set()).add((line, outcome))

    result: dict[GenericCallableAccessibleObject, TargetDiagnosis] = {}
    for gao in ranges:
        gao_lines = sorted(lines.get(gao, ()))
        gao_branches = sorted(branches.get(gao, ()))
        if not gao_lines and not gao_branches:
            continue
        kept_lines = gao_lines[:MAX_GOALS_PER_TARGET]
        kept_branches = gao_branches[: MAX_GOALS_PER_TARGET - len(kept_lines)]
        result[gao] = TargetDiagnosis(
            uncovered_lines=tuple(kept_lines),
            missing_branches=tuple(kept_branches),
            omitted_goals=len(gao_lines) + len(gao_branches) - len(kept_lines) - len(kept_branches),
        )
    return result


def format_line_numbers(lines: Sequence[int]) -> str:
    """Formats ascending line numbers, joining consecutive runs into ranges.

    Args:
        lines: Ascending line numbers.

    Returns:
        For example ``"3, 7-9, 12"``.
    """
    parts: list[str] = []
    index = 0
    while index < len(lines):
        end = index
        while end + 1 < len(lines) and lines[end + 1] == lines[end] + 1:
            end += 1
        parts.append(str(lines[index]) if end == index else f"{lines[index]}-{lines[end]}")
        index = end + 1
    return ", ".join(parts)


def describe(diagnosis: TargetDiagnosis) -> list[str]:
    """The prompt lines that describe a diagnosis, one fact per line.

    Args:
        diagnosis: The diagnosis.

    Returns:
        The lines, without list markers or indentation.
    """
    described: list[str] = []
    if diagnosis.uncovered_lines:
        described.append(f"Uncovered lines: {format_line_numbers(diagnosis.uncovered_lines)}")
    if diagnosis.missing_branches:
        outcomes = ", ".join(
            f"line {line} ({outcome})" for line, outcome in diagnosis.missing_branches
        )
        described.append(f"Branch outcomes never taken: {outcomes}")
    if diagnosis.omitted_goals:
        described.append(f"... and {diagnosis.omitted_goals} more uncovered goals")
    described.extend(f"Hint: {hint}" for hint in diagnosis.hints)
    return described
