# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Problem cards: typed diagnoses of why a callable is still uncovered.

An extractor derives cards of one type from what the search knows about a callable:
its line coverage, the uncovered goals, the control dependence graph and the
executions of the current test cases. The :class:`ProblemCardBuilder` runs the
enabled extractors, removes duplicates and recently sent cards, and keeps per-type
counters of how the cards fared.
"""

from __future__ import annotations

import collections
import dataclasses
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

import libcst as cst

from pynguin.analyses.typesystem import Instance, NoneType, UnionType
from pynguin.configuration import ProblemCardType
from pynguin.ga.coveragegoals import BranchGoal

if TYPE_CHECKING:
    from collections.abc import Collection, Hashable, Iterable, Mapping, Sequence

    import pynguin.ga.computations as ff
    import pynguin.ga.testcasechromosome as tcc
    from pynguin.analyses.typesystem import ProperType
    from pynguin.instrumentation.controlflow import BasicBlockNode
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.testcase.execution_result import ExecutionResult
    from pynguin.testcase.testcase import Statement, TestCase
    from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject
    from pynguin.utils.report import LineAnnotation

# How many characters of an exception message or statement a card quotes.
_MAX_QUOTE = 80


@dataclasses.dataclass(frozen=True)
class ProblemCard:
    """One diagnosis of why a callable is uncovered.

    Attributes:
        type: The kind of diagnosis.
        target: The callable the card is about.
        detail: What identifies the card among the cards of its type and target,
            e.g. the line of a condition; used to remove duplicates.
        text: The hint shown in the prompt.
    """

    type: ProblemCardType
    target: GenericCallableAccessibleObject = dataclasses.field(compare=False)
    detail: Hashable
    text: str = dataclasses.field(compare=False)

    @property
    def key(self) -> tuple[int, ProblemCardType, Hashable]:
        """The identity of the card, for removing duplicates and repeats.

        Returns:
            The key.
        """
        return id(self.target), self.type, self.detail


@dataclasses.dataclass(frozen=True)
class ProblemCardContext:
    """What an extractor knows about one target callable.

    Attributes:
        target: The callable.
        source_range: Its first and last source line.
        line_annotations: Per-line coverage annotations for the module.
        uncovered_goals: All goals that are not covered yet.
        subject_properties: The properties of the subject under test.
        executions: The current test cases with their last execution result.
    """

    target: GenericCallableAccessibleObject
    source_range: tuple[int, int]
    line_annotations: Sequence[LineAnnotation]
    uncovered_goals: Collection[ff.FitnessFunction]
    subject_properties: SubjectProperties
    executions: Sequence[tuple[TestCase, ExecutionResult]]


ProblemCardExtractor = Callable[[ProblemCardContext], "list[ProblemCard]"]


def _in_range(context: ProblemCardContext, line: int) -> bool:
    start, end = context.source_range
    return start <= line <= end


def _quote(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _MAX_QUOTE else text[: _MAX_QUOTE - 3] + "..."


def _describe_exception(exception: BaseException) -> str:
    message = str(exception)
    name = type(exception).__name__
    return f"{name}: {_quote(message)}" if message else name


def _statement_code(statement: Statement) -> str:
    return _quote(cst.Module(body=[]).code_for_node(statement.node))


def _calls_of_target(
    context: ProblemCardContext,
) -> list[tuple[TestCase, ExecutionResult, int]]:
    """The executions that contain a call of the target, with the call's position.

    Args:
        context: The context.

    Returns:
        ``(test case, result, position of the first call)`` per such execution.
    """
    calls = []
    for test_case, result in context.executions:
        for position, statement in enumerate(test_case.statements()):
            if statement.accessible is context.target:
                calls.append((test_case, result, position))
                break
    return calls


def extract_unreached_callable(context: ProblemCardContext) -> list[ProblemCard]:
    """A card if none of the callable's lines were covered.

    Args:
        context: The context.

    Returns:
        At most one card.
    """
    covered = total = 0
    for annotation in context.line_annotations:
        if _in_range(context, annotation.line_no):
            covered += annotation.total.covered
            total += annotation.total.existing
    if total == 0 or covered > 0:
        return []
    return [
        ProblemCard(
            ProblemCardType.UNREACHED_CALLABLE,
            context.target,
            None,
            "never reached; the setup likely fails before the call is made -- "
            "construct valid inputs/state and invoke it directly",
        )
    ]


def extract_branch_polarity_gap(context: ProblemCardContext) -> list[ProblemCard]:
    """A card if a branch inside the callable only took one outcome.

    Args:
        context: The context.

    Returns:
        At most one card, naming all such branch lines.
    """
    lines = tuple(
        annotation.line_no
        for annotation in context.line_annotations
        if _in_range(context, annotation.line_no)
        and annotation.branches.existing > 0
        and 0 < annotation.branches.covered < annotation.branches.existing
    )
    if not lines:
        return []
    lines_str = ", ".join(str(line) for line in lines)
    return [
        ProblemCard(
            ProblemCardType.BRANCH_POLARITY_GAP,
            context.target,
            lines,
            f"branch(es) at line(s) {lines_str} only took one outcome -- "
            "vary one input/state axis to trigger the opposite outcome",
        )
    ]


def extract_exception_barrier(context: ProblemCardContext) -> list[ProblemCard]:
    """A card if every test that calls the callable raises before the call.

    Args:
        context: The context.

    Returns:
        At most one card, for the most frequent failing statement and exception.
    """
    barriers: collections.Counter[tuple[str, str]] = collections.Counter()
    for test_case, result, position in _calls_of_target(context):
        failed_at = min(result.exceptions, default=None)
        if failed_at is None or failed_at >= position:
            return []  # One test reaches the call, so the setup can work.
        statement = test_case.get_statement(failed_at)
        barriers[_statement_code(statement), _describe_exception(result.exceptions[failed_at])] += 1
    if not barriers:
        return []
    (code, exception), _ = barriers.most_common(1)[0]
    return [
        ProblemCard(
            ProblemCardType.EXCEPTION_BARRIER,
            context.target,
            (code, exception),
            f"tests fail before the call: `{code}` raises {exception} -- "
            "prepare the arguments or object state that this setup step needs",
        )
    ]


def _predicates_by_node(
    subject_properties: SubjectProperties, code_object_id: int
) -> dict[BasicBlockNode, int]:
    return {
        meta.node: predicate_id
        for predicate_id, meta in subject_properties.existing_predicates.items()
        if meta.code_object_id == code_object_id and not getattr(meta, "is_auxiliary", False)
    }


def _never_evaluated(predicate_id: int, uncovered: set[BranchGoal]) -> bool:
    return (
        BranchGoal(0, predicate_id, value=True) in uncovered
        and BranchGoal(0, predicate_id, value=False) in uncovered
    )


def extract_cdg_bottleneck(context: ProblemCardContext) -> list[ProblemCard]:
    """Cards for conditions that are never evaluated because of an earlier condition.

    For a condition in the callable that never took either outcome, walk up its
    control dependencies to the nearest condition that was evaluated but never took
    the outcome the blocked condition depends on.

    Args:
        context: The context.

    Returns:
        One card per bottleneck condition and outcome.
    """
    properties = context.subject_properties
    uncovered: set[BranchGoal] = {
        goal
        for fitness in context.uncovered_goals
        if isinstance(goal := getattr(fitness, "goal", None), BranchGoal)
    }
    cards: dict[tuple[int, bool], ProblemCard] = {}
    for blocked_id in sorted({goal.predicate_id for goal in uncovered}):
        blocked = properties.existing_predicates.get(blocked_id)
        if (
            blocked is None
            or not _in_range(context, blocked.line_no)
            or not _never_evaluated(blocked_id, uncovered)
        ):
            continue
        code_object = properties.existing_code_objects[blocked.code_object_id]
        by_node = _predicates_by_node(properties, blocked.code_object_id)
        pending, visited = [blocked.node], set()
        while pending:
            node = pending.pop()
            if node in visited:
                continue
            visited.add(node)
            for dependency in code_object.cdg.get_control_dependencies(node):
                parent_id = by_node.get(dependency.node)
                if parent_id is None:
                    continue
                if not _never_evaluated(parent_id, uncovered):
                    if BranchGoal(0, parent_id, value=dependency.branch_value) in uncovered:
                        parent_line = properties.existing_predicates[parent_id].line_no
                        value = dependency.branch_value
                        cards.setdefault(
                            (parent_id, value),
                            ProblemCard(
                                ProblemCardType.CDG_BOTTLENECK,
                                context.target,
                                (parent_line, value),
                                f"the condition at line {blocked.line_no} is only evaluated "
                                f"when the condition at line {parent_line} is {value}, "
                                f"which no test achieved -- make it {value} first",
                            ),
                        )
                else:
                    pending.append(dependency.node)
    return list(cards.values())


def _raw_type(proper_type: ProperType) -> type | None:
    if isinstance(proper_type, Instance):
        raw = proper_type.type.raw_type
        return raw if isinstance(raw, type) else None
    if isinstance(proper_type, NoneType):
        return type(None)
    return None


_LITERAL_TYPES: dict[type[cst.BaseExpression], type] = {
    cst.Integer: int,
    cst.Float: float,
    cst.Imaginary: complex,
    cst.SimpleString: str,
    cst.ConcatenatedString: str,
    cst.FormattedString: str,
    cst.List: list,
    cst.Dict: dict,
    cst.Set: set,
    cst.Tuple: tuple,
}


def _argument_type(value: cst.BaseExpression, bound_types: Mapping[str, type]) -> type | None:
    if isinstance(value, cst.Name):
        if value.value in {"True", "False"}:
            return bool
        if value.value == "None":
            return type(None)
        return bound_types.get(value.value)
    return _LITERAL_TYPES.get(type(value))


def _call_of(statement: Statement) -> cst.Call | None:
    node = statement.node
    if not isinstance(node, cst.SimpleStatementLine) or not node.body:
        return None
    small = node.body[0]
    value = small.value if isinstance(small, cst.Assign | cst.Expr) else None
    if isinstance(value, cst.Await):
        value = value.expression
    return value if isinstance(value, cst.Call) else None


def extract_type_never_attempted(context: ProblemCardContext) -> list[ProblemCard]:
    """Cards for union-typed parameters with member types that no test passed.

    Only parameters for which at least one argument type is known are considered.

    Args:
        context: The context.

    Returns:
        One card per such parameter.
    """
    parameters = context.target.inferred_signature.original_parameters
    names = list(parameters)
    observed: dict[str, set[type]] = collections.defaultdict(set)
    for test_case, _, position in _calls_of_target(context):
        statements = test_case.statements()
        bound_types = {
            statement.bound_variable: statement.bound_type
            for statement in statements[:position]
            if statement.bound_variable is not None and statement.bound_type is not None
        }
        call = _call_of(statements[position])
        if call is None:
            continue
        for index, argument in enumerate(call.args):
            if argument.star:
                continue
            name = argument.keyword.value if argument.keyword is not None else None
            if name is None and index < len(names):
                name = names[index]
            argument_type = _argument_type(argument.value, bound_types)
            if name is not None and argument_type is not None:
                observed[name].add(argument_type)

    cards = []
    for name, parameter_type in parameters.items():
        if not isinstance(parameter_type, UnionType) or not observed.get(name):
            continue
        missing = [
            member
            for member in parameter_type.items
            if (raw := _raw_type(member)) is not None
            and not any(issubclass(seen, raw) for seen in observed[name])
        ]
        if missing:
            missing_str = ", ".join(str(member) for member in missing)
            cards.append(
                ProblemCard(
                    ProblemCardType.TYPE_NEVER_ATTEMPTED,
                    context.target,
                    name,
                    f"parameter `{name}` accepts {parameter_type}, but no test passed "
                    f"{missing_str} -- call it with such a value",
                )
            )
    return cards


def extract_environment_barrier(context: ProblemCardContext) -> list[ProblemCard]:
    """A card if calls of the callable fail with a file system or network error.

    Args:
        context: The context.

    Returns:
        At most one card, for the most frequent such error.
    """
    errors: collections.Counter[str] = collections.Counter()
    for _, result, position in _calls_of_target(context):
        for failed_at, exception in result.exceptions.items():
            if failed_at >= position and isinstance(exception, OSError):
                errors[_describe_exception(exception)] += 1
    if not errors:
        return []
    error = errors.most_common(1)[0][0]
    return [
        ProblemCard(
            ProblemCardType.ENVIRONMENT_BARRIER,
            context.target,
            error.split(":", 1)[0],
            f"calls fail with {error} -- it needs files or the network; create files "
            "under pytest's `tmp_path` or pass in-memory objects such as `io.StringIO`, "
            "since tests have no network access",
        )
    ]


# The built-in extractor of each card type.
EXTRACTORS: dict[ProblemCardType, ProblemCardExtractor] = {
    ProblemCardType.UNREACHED_CALLABLE: extract_unreached_callable,
    ProblemCardType.BRANCH_POLARITY_GAP: extract_branch_polarity_gap,
    ProblemCardType.EXCEPTION_BARRIER: extract_exception_barrier,
    ProblemCardType.CDG_BOTTLENECK: extract_cdg_bottleneck,
    ProblemCardType.TYPE_NEVER_ATTEMPTED: extract_type_never_attempted,
    ProblemCardType.ENVIRONMENT_BARRIER: extract_environment_barrier,
}


@dataclasses.dataclass
class ProblemCardStats:
    """How the cards of one type fared over a run.

    A query's test cases and the goals they cover count for every card the query
    contained.

    Attributes:
        extracted: Cards the extractor derived.
        selected: Cards kept after removing duplicates, repeats and excess cards.
        published: Selected cards that were sent to the LLM.
        admitted: Test cases parsed from the answers to queries with such a card.
        survived: Of those test cases, the ones in the final archive.
        coverage_gain: Goals that surviving test cases cover in the final archive.
    """

    extracted: int = 0
    selected: int = 0
    published: int = 0
    admitted: int = 0
    survived: int = 0
    coverage_gain: int = 0

    def __str__(self) -> str:
        return "/".join(str(value) for value in dataclasses.astuple(self))


class ProblemCardBuilder:
    """Selects the problem cards for the targets of each uncovered-targets query."""

    def __init__(
        self,
        card_types: Iterable[ProblemCardType],
        *,
        max_cards_per_target: int = 3,
        cooldown: int = 0,
        extractors: Mapping[ProblemCardType, ProblemCardExtractor] | None = None,
    ) -> None:
        """Creates a builder.

        Args:
            card_types: The enabled card types, in order of priority.
            max_cards_per_target: The maximum number of cards per target.
            cooldown: The number of queries after a query that do not repeat its
                cards; 0 never suppresses a card.
            extractors: The extractor of each card type; defaults to ``EXTRACTORS``.
        """
        self._card_types = list(dict.fromkeys(card_types))
        self._max_cards_per_target = max_cards_per_target
        self._cooldown = cooldown
        self._extractors = dict(EXTRACTORS if extractors is None else extractors)
        self._lock = threading.Lock()
        self._published_queries = 0
        self._last_published: dict[Hashable, int] = {}
        self._admitted: list[tuple[tuple[ProblemCard, ...], list[tcc.TestCaseChromosome]]] = []
        self.stats: dict[ProblemCardType, ProblemCardStats] = {
            card_type: ProblemCardStats() for card_type in self._card_types
        }

    def build(
        self, contexts: Iterable[ProblemCardContext]
    ) -> dict[GenericCallableAccessibleObject, tuple[ProblemCard, ...]]:
        """Derives and selects the cards for the given targets.

        Args:
            contexts: One context per target.

        Returns:
            The selected cards of each target that has any.
        """
        selected: dict[GenericCallableAccessibleObject, tuple[ProblemCard, ...]] = {}
        with self._lock:
            for context in contexts:
                cards: list[ProblemCard] = []
                seen: set[Hashable] = set()
                for card_type in self._card_types:
                    extractor = self._extractors.get(card_type)
                    if extractor is None:
                        continue
                    for card in extractor(context):
                        self.stats[card_type].extracted += 1
                        if (
                            card.key in seen
                            or self._is_cooling_down(card)
                            or len(cards) >= self._max_cards_per_target
                        ):
                            continue
                        seen.add(card.key)
                        cards.append(card)
                        self.stats[card_type].selected += 1
                if cards:
                    selected[context.target] = tuple(cards)
        return selected

    def _is_cooling_down(self, card: ProblemCard) -> bool:
        last = self._last_published.get(card.key)
        return (
            self._cooldown > 0
            and last is not None
            and self._published_queries - last < self._cooldown
        )

    def mark_published(self, cards: Sequence[ProblemCard]) -> None:
        """Records that a query with the given cards was sent.

        Args:
            cards: The cards of the query.
        """
        with self._lock:
            self._published_queries += 1
            for card in cards:
                self._last_published[card.key] = self._published_queries
                if card.type in self.stats:
                    self.stats[card.type].published += 1

    def record_admitted(
        self, cards: Sequence[ProblemCard], chromosomes: list[tcc.TestCaseChromosome]
    ) -> None:
        """Records the test cases parsed from the answer to a query.

        Args:
            cards: The cards of the query.
            chromosomes: The test cases parsed from the answer.
        """
        if not cards:
            return
        with self._lock:
            for card in cards:
                if card.type in self.stats:
                    self.stats[card.type].admitted += len(chromosomes)
            self._admitted.append((tuple(cards), chromosomes))

    def record_survivors(
        self,
        solutions: Iterable[tcc.TestCaseChromosome],
        covered_goals: Mapping[ff.TestCaseFitnessFunction, tcc.TestCaseChromosome],
    ) -> None:
        """Counts the admitted test cases that made it into the final archive.

        Args:
            solutions: The final archive's test cases.
            covered_goals: The test case that covers each covered goal.
        """
        in_archive = {id(solution) for solution in solutions}
        goals_per_solution = collections.Counter(id(c) for c in covered_goals.values())
        with self._lock:
            for cards, chromosomes in self._admitted:
                survived = [c for c in chromosomes if id(c) in in_archive]
                gain = sum(goals_per_solution[id(c)] for c in survived)
                for card in cards:
                    if card.type in self.stats:
                        self.stats[card.type].survived += len(survived)
                        self.stats[card.type].coverage_gain += gain
            self._admitted.clear()

    def format_stats(self) -> str:
        """The counters of all enabled card types on one line.

        Returns:
            ``TYPE=extracted/selected/published/admitted/survived/coverage_gain``
            entries separated by ``;``.
        """
        with self._lock:
            return ";".join(f"{card_type.value}={stats}" for card_type, stats in self.stats.items())
