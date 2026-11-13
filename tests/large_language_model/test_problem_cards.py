#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the problem cards, one per card type on a small fixture module."""

from __future__ import annotations

import importlib
import inspect
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import libcst as cst
import pytest

import pynguin.configuration as config
from pynguin.analyses.type_inference import HintInference
from pynguin.analyses.typesystem import TypeSystem
from pynguin.configuration import ProblemCardType
from pynguin.ga.coveragegoals import BranchGoalPool
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import BranchCoverageInstrumentation
from pynguin.large_language_model.problem_cards import (
    ProblemCard,
    ProblemCardBuilder,
    ProblemCardContext,
    extract_branch_polarity_gap,
    extract_cdg_bottleneck,
    extract_environment_barrier,
    extract_exception_barrier,
    extract_type_never_attempted,
    extract_unreached_callable,
)
from pynguin.testcase.execution_result import ExecutionResult
from pynguin.testcase.testcase import Statement, TestCase
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.report import CoverageEntry, LineAnnotation

if TYPE_CHECKING:
    import types

FIXTURE = "tests.fixtures.examples.problem_cards"


@pytest.fixture(scope="module")
def module() -> types.ModuleType:
    return importlib.import_module(FIXTURE)


def _function(function) -> GenericFunction:
    signature = TypeSystem().infer_type_info(function, HintInference())
    return GenericFunction(function, signature)


def _range(function) -> tuple[int, int]:
    lines, start = inspect.getsourcelines(function)
    return start, start + len(lines) - 1


def _line_of(function, text: str) -> int:
    lines, start = inspect.getsourcelines(function)
    return start + next(i for i, line in enumerate(lines) if text in line)


def _annotation(line_no: int, existing: int, covered: int, branches=(0, 0)) -> LineAnnotation:
    return LineAnnotation(
        line_no=line_no,
        total=CoverageEntry(existing=existing, covered=covered),
        branches=CoverageEntry(existing=branches[0], covered=branches[1]),
        branchless_code_objects=CoverageEntry(existing=0, covered=0),
        lines=CoverageEntry(existing=0, covered=0),
    )


def _context(target, function, **kwargs) -> ProblemCardContext:
    defaults = {
        "line_annotations": [],
        "uncovered_goals": [],
        "subject_properties": SubjectProperties(),
        "executions": [],
    }
    defaults.update(kwargs)
    return ProblemCardContext(target=target, source_range=_range(function), **defaults)


def _statement(code: str, *, bound_type=None, accessible=None) -> Statement:
    node = cst.parse_statement(code)
    assert isinstance(node, cst.SimpleStatementLine)
    small = node.body[0]
    bound = None
    if isinstance(small, cst.Assign):
        target = small.targets[0].target
        assert isinstance(target, cst.Name)
        bound = target.value
    return Statement(node=node, bound_variable=bound, bound_type=bound_type, accessible=accessible)


def _execution(
    *statements: Statement, raised: dict[int, BaseException] | None = None
) -> tuple[TestCase, ExecutionResult]:
    test_case = TestCase()
    for statement in statements:
        test_case.add_statement(statement)
    result = ExecutionResult()
    for position, exception in (raised or {}).items():
        result.report_new_thrown_exception(position, exception)
    return test_case, result


def test_unreached_callable(module):
    target = _function(module.never_called)
    start, end = _range(module.never_called)

    cards = extract_unreached_callable(
        _context(
            target,
            module.never_called,
            line_annotations=[_annotation(start, 1, 0), _annotation(end, 2, 0)],
        )
    )
    reached = extract_unreached_callable(
        _context(target, module.never_called, line_annotations=[_annotation(end, 2, 1)])
    )

    assert [card.type for card in cards] == [ProblemCardType.UNREACHED_CALLABLE]
    assert "never reached" in cards[0].text
    assert reached == []


def test_branch_polarity_gap(module):
    target = _function(module.sign)
    condition = _line_of(module.sign, "if value > 0")

    cards = extract_branch_polarity_gap(
        _context(
            target,
            module.sign,
            line_annotations=[_annotation(condition, 3, 2, branches=(2, 1))],
        )
    )
    fully_covered = extract_branch_polarity_gap(
        _context(
            target,
            module.sign,
            line_annotations=[_annotation(condition, 3, 3, branches=(2, 2))],
        )
    )

    assert [card.type for card in cards] == [ProblemCardType.BRANCH_POLARITY_GAP]
    assert f"line(s) {condition} only took one outcome" in cards[0].text
    assert fully_covered == []


def test_exception_barrier(module):
    target = MagicMock()
    failing = _execution(
        _statement("int_0 = -5", bound_type=int),
        _statement("account_0 = Account(int_0)"),
        _statement("int_1 = account_0.withdraw(int_0)", accessible=target),
        raised={1: ValueError("negative balance")},
    )

    cards = extract_exception_barrier(
        _context(target, module.Account.withdraw, executions=[failing])
    )

    assert [card.type for card in cards] == [ProblemCardType.EXCEPTION_BARRIER]
    assert "`account_0 = Account(int_0)` raises ValueError: negative balance" in cards[0].text


def test_no_exception_barrier_when_a_test_reaches_the_call(module):
    target = MagicMock()
    failing = _execution(
        _statement("account_0 = Account(-1)"),
        _statement("account_0.withdraw(1)", accessible=target),
        raised={0: ValueError("negative balance")},
    )
    passing = _execution(
        _statement("account_0 = Account(5)"),
        _statement("account_0.withdraw(1)", accessible=target),
    )

    assert (
        extract_exception_barrier(
            _context(target, module.Account.withdraw, executions=[failing, passing])
        )
        == []
    )


def _instrumented(module, function_name: str) -> SubjectProperties:
    subject_properties = SubjectProperties()
    transformer = InstrumentationTransformer(
        subject_properties,
        [BranchCoverageInstrumentation(subject_properties)],
        to_cover_config=config.ToCoverConfiguration(),
    )
    function = getattr(module, function_name)
    transformer.instrument_code(function.__code__)
    return subject_properties


def test_cdg_bottleneck(module):
    subject_properties = _instrumented(module, "nested")
    outer_line = _line_of(module.nested, "if x == 1337")
    inner_line = _line_of(module.nested, "if y > 0")
    goals = BranchGoalPool(subject_properties).branch_goals
    # The outer condition was only ever False, so the inner one never ran.
    uncovered = [
        MagicMock(goal=goal)
        for goal in goals
        if subject_properties.existing_predicates[goal.predicate_id].line_no == inner_line
        or goal.value
    ]

    cards = extract_cdg_bottleneck(
        _context(
            MagicMock(),
            module.nested,
            uncovered_goals=uncovered,
            subject_properties=subject_properties,
        )
    )

    assert [card.type for card in cards] == [ProblemCardType.CDG_BOTTLENECK]
    assert cards[0].detail == (outer_line, True)
    assert f"line {inner_line} is only evaluated when the condition at line {outer_line}" in (
        cards[0].text
    )


def test_no_cdg_bottleneck_when_every_condition_was_evaluated(module):
    subject_properties = _instrumented(module, "nested")
    goals = BranchGoalPool(subject_properties).branch_goals
    # Each condition missed one outcome only: no condition is blocked.
    uncovered = [MagicMock(goal=goal) for goal in goals if goal.value]

    assert (
        extract_cdg_bottleneck(
            _context(
                MagicMock(),
                module.nested,
                uncovered_goals=uncovered,
                subject_properties=subject_properties,
            )
        )
        == []
    )


def test_type_never_attempted(module):
    target = _function(module.describe)
    executions = [
        _execution(
            _statement("int_0 = 3", bound_type=int),
            _statement("str_0 = describe(int_0)", accessible=target),
        ),
        _execution(_statement("str_0 = describe(value=None)", accessible=target)),
    ]

    cards = extract_type_never_attempted(_context(target, module.describe, executions=executions))

    assert [card.type for card in cards] == [ProblemCardType.TYPE_NEVER_ATTEMPTED]
    assert cards[0].detail == "value"
    assert "no test passed str" in cards[0].text


def test_type_never_attempted_needs_known_argument_types(module):
    target = _function(module.describe)
    unknown = _execution(_statement("str_0 = describe(var_0)", accessible=target))

    assert (
        extract_type_never_attempted(_context(target, module.describe, executions=[unknown])) == []
    )


def test_environment_barrier(module):
    target = MagicMock()
    executions = [
        _execution(
            _statement("str_0 = 'config.ini'", bound_type=str),
            _statement("str_1 = read_config(str_0)", accessible=target),
            raised={1: FileNotFoundError(2, "No such file or directory")},
        ),
        _execution(
            _statement("str_1 = read_config(None)", accessible=target),
            raised={0: TypeError("expected str")},
        ),
    ]

    cards = extract_environment_barrier(_context(target, module.read_config, executions=executions))

    assert [card.type for card in cards] == [ProblemCardType.ENVIRONMENT_BARRIER]
    assert "FileNotFoundError" in cards[0].text
    assert "tmp_path" in cards[0].text


def _card(card_type, target, detail) -> ProblemCard:
    return ProblemCard(card_type, target, detail, f"{card_type.value} {detail}")


def _builder_context(target) -> ProblemCardContext:
    return ProblemCardContext(target, (1, 2), [], [], SubjectProperties(), [])


def test_builder_orders_deduplicates_and_caps_cards():
    target = MagicMock()
    extractors = {
        ProblemCardType.BRANCH_POLARITY_GAP: lambda ctx: [
            _card(ProblemCardType.BRANCH_POLARITY_GAP, ctx.target, 1),
            _card(ProblemCardType.BRANCH_POLARITY_GAP, ctx.target, 1),
        ],
        ProblemCardType.UNREACHED_CALLABLE: lambda ctx: [
            _card(ProblemCardType.UNREACHED_CALLABLE, ctx.target, None)
        ],
        ProblemCardType.CDG_BOTTLENECK: lambda ctx: [
            _card(ProblemCardType.CDG_BOTTLENECK, ctx.target, 7)
        ],
    }
    builder = ProblemCardBuilder(
        [
            ProblemCardType.UNREACHED_CALLABLE,
            ProblemCardType.BRANCH_POLARITY_GAP,
            ProblemCardType.CDG_BOTTLENECK,
            ProblemCardType.TYPE_NEVER_ATTEMPTED,
        ],
        max_cards_per_target=2,
        extractors=extractors,
    )

    cards = builder.build([_builder_context(target)])

    assert [card.type for card in cards[target]] == [
        ProblemCardType.UNREACHED_CALLABLE,
        ProblemCardType.BRANCH_POLARITY_GAP,
    ]
    assert builder.stats[ProblemCardType.BRANCH_POLARITY_GAP].extracted == 2
    assert builder.stats[ProblemCardType.BRANCH_POLARITY_GAP].selected == 1
    assert builder.stats[ProblemCardType.CDG_BOTTLENECK].selected == 0


def test_builder_suppresses_recently_published_cards():
    target = MagicMock()
    extractors = {
        ProblemCardType.UNREACHED_CALLABLE: lambda ctx: [
            _card(ProblemCardType.UNREACHED_CALLABLE, ctx.target, None)
        ]
    }
    builder = ProblemCardBuilder(
        [ProblemCardType.UNREACHED_CALLABLE], cooldown=2, extractors=extractors
    )

    first = builder.build([_builder_context(target)])
    builder.mark_published(first[target])
    # The next two queries do not repeat the card; the third one may.
    assert builder.build([_builder_context(target)]) == {}
    builder.mark_published([])
    assert builder.build([_builder_context(target)]) == {}
    builder.mark_published([])
    assert target in builder.build([_builder_context(target)])


def test_builder_without_cooldown_repeats_cards(module):
    target = _function(module.never_called)
    start, _ = _range(module.never_called)
    context = _context(target, module.never_called, line_annotations=[_annotation(start, 1, 0)])
    builder = ProblemCardBuilder([ProblemCardType.UNREACHED_CALLABLE])

    builder.mark_published(builder.build([context])[target])

    assert target in builder.build([context])


def test_builder_stats_follow_published_cards_to_the_archive():
    target = MagicMock()
    card = _card(ProblemCardType.EXCEPTION_BARRIER, target, "x")
    builder = ProblemCardBuilder(
        [ProblemCardType.EXCEPTION_BARRIER, ProblemCardType.UNREACHED_CALLABLE],
        extractors={ProblemCardType.EXCEPTION_BARRIER: lambda _: [card]},
    )
    kept, dropped = MagicMock(), MagicMock()

    builder.build([_builder_context(target)])
    builder.mark_published([card])
    builder.record_admitted([card], [kept, dropped])
    builder.record_admitted([], [MagicMock()])
    builder.record_survivors([kept, MagicMock()], {"goal 1": kept, "goal 2": kept})

    assert builder.format_stats() == (
        "EXCEPTION_BARRIER=1/1/1/2/1/2;UNREACHED_CALLABLE=0/0/0/0/0/0"
    )
