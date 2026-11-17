#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Computes an edit distance between a string and the language of a regular expression.

The matching of regular expressions happens in the uninstrumented ``_sre`` engine, so
a predicate like ``PATTERN.match(s) is None`` only yields a distance of 0 or 1. This
module provides a gradient instead: the minimum number of character insertions,
deletions and substitutions that make ``s`` match the pattern.

The pattern is parsed with the parser of the :mod:`re` module and translated into a
Thompson NFA. The edit distance is then computed with a dynamic program over the
string positions and the NFA states. Some constructs are approximated (assertions,
word boundaries and possessive repeats are treated as if they always succeed);
backreferences and conditional groups are not supported. The distance is only a
heuristic, but it is 0 if and only if :mod:`re` reports a match, because callers
only use it for non-matching strings and clamp it to at least 1.
"""

from __future__ import annotations

import enum
import functools
import re
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if sys.version_info >= (3, 11):
    import re._constants as sre_constants
    import re._parser as sre_parse
else:  # pragma: no cover
    import sre_constants
    import sre_parse

if TYPE_CHECKING:
    from collections.abc import Callable

# Upper bounds that keep the computation cheap, as it runs during test execution.
MAX_NFA_STATES = 2000
MAX_STRING_LENGTH = 256
MAX_UNROLLED_REPEAT = 32


class RegexMethod(enum.Enum):
    """The regex methods whose semantics the distance supports."""

    MATCH = "match"
    SEARCH = "search"
    FULLMATCH = "fullmatch"


class _UnsupportedPatternError(Exception):
    """Raised if a pattern uses a construct that is not supported."""


class _Anchor(enum.Enum):
    BEGIN = enum.auto()
    BEGIN_LINE = enum.auto()
    END = enum.auto()
    END_LINE = enum.auto()
    END_STRING = enum.auto()


@dataclass
class _State:
    epsilons: list[tuple[int, _Anchor | None]] = field(default_factory=list)
    chars: list[tuple[Callable[[str], bool], int]] = field(default_factory=list)


class _Nfa:
    """A Thompson NFA with character-predicate and anchored epsilon transitions."""

    def __init__(self) -> None:
        self.states: list[_State] = []
        self.start = self.new_state()
        self.accept = self.start

    def new_state(self) -> int:
        if len(self.states) >= MAX_NFA_STATES:
            raise _UnsupportedPatternError("Pattern is too large")
        self.states.append(_State())
        return len(self.states) - 1

    def add_epsilon(self, source: int, target: int, anchor: _Anchor | None = None) -> None:
        self.states[source].epsilons.append((target, anchor))

    def add_char(self, source: int, target: int, predicate: Callable[[str], bool]) -> None:
        self.states[source].chars.append((predicate, target))


def _is_word(char: str, *, ascii_only: bool) -> bool:
    if ascii_only and not char.isascii():
        return False
    return char.isalnum() or char == "_"


def _is_digit(char: str, *, ascii_only: bool) -> bool:
    if ascii_only:
        return "0" <= char <= "9"
    return char.isdecimal()


def _is_space(char: str, *, ascii_only: bool) -> bool:
    if ascii_only:
        return char in " \t\n\r\f\v"
    return char.isspace()


def _category_predicate(category: Any, *, ascii_only: bool) -> Callable[[str], bool]:
    name = str(category)
    base: Callable[[str], bool]
    if name.endswith("DIGIT"):
        base = functools.partial(_is_digit, ascii_only=ascii_only)
    elif name.endswith("SPACE"):
        base = functools.partial(_is_space, ascii_only=ascii_only)
    elif name.endswith("WORD"):
        base = functools.partial(_is_word, ascii_only=ascii_only)
    elif name.endswith("LINEBREAK"):

        def base(char: str) -> bool:
            return char == "\n"

    else:
        raise _UnsupportedPatternError(f"Unsupported category {name}")
    if "_NOT_" in name:
        return lambda char: not base(char)
    return base


def _case_variants(char: str) -> set[str]:
    return {char, char.lower(), char.upper(), char.casefold()}


def _with_ignore_case(
    predicate: Callable[[str], bool], *, ignore_case: bool
) -> Callable[[str], bool]:
    if not ignore_case:
        return predicate
    return lambda char: any(predicate(variant) for variant in _case_variants(char))


def _in_range(low: str, high: str, char: str) -> bool:
    return low <= char <= high


def _set_predicate(items: list[tuple[Any, Any]], flags: int) -> Callable[[str], bool]:
    ascii_only = bool(flags & re.ASCII)
    negate = False
    members: list[Callable[[str], bool]] = []
    for op, arg in items:
        if op is sre_constants.NEGATE:
            negate = True
        elif op is sre_constants.LITERAL:
            members.append(functools.partial(str.__eq__, chr(arg)))
        elif op is sre_constants.RANGE:
            members.append(functools.partial(_in_range, chr(arg[0]), chr(arg[1])))
        elif op is sre_constants.CATEGORY:
            members.append(_category_predicate(arg, ascii_only=ascii_only))
        else:
            raise _UnsupportedPatternError(f"Unsupported set item {op}")

    def contains(char: str) -> bool:
        return any(member(char) for member in members)

    contained = _with_ignore_case(contains, ignore_case=bool(flags & re.IGNORECASE))
    if negate:
        return lambda char: not contained(char)
    return contained


class _NfaBuilder:
    """Translates the parse tree of the re module into an NFA."""

    def __init__(self, nfa: _Nfa) -> None:
        self._nfa = nfa

    def build_sequence(self, items: Any, start: int, flags: int) -> int:
        current = start
        for op, arg in items:
            current = self._build_item(op, arg, current, flags)
        return current

    def _char(self, current: int, predicate: Callable[[str], bool]) -> int:
        target = self._nfa.new_state()
        self._nfa.add_char(current, target, predicate)
        return target

    def _build_item(self, op: Any, arg: Any, current: int, flags: int) -> int:  # noqa: C901
        ignore_case = bool(flags & re.IGNORECASE)
        name = str(op)
        if op is sre_constants.LITERAL:
            literal = chr(arg)
            return self._char(
                current,
                _with_ignore_case(functools.partial(str.__eq__, literal), ignore_case=ignore_case),
            )
        if op is sre_constants.NOT_LITERAL:
            literal = chr(arg)
            equal = _with_ignore_case(
                functools.partial(str.__eq__, literal), ignore_case=ignore_case
            )
            return self._char(current, lambda char: not equal(char))
        if op is sre_constants.ANY:
            if flags & re.DOTALL:
                return self._char(current, lambda _: True)
            return self._char(current, lambda char: char != "\n")
        if op is sre_constants.IN:
            return self._char(current, _set_predicate(arg, flags))
        if op is sre_constants.AT:
            return self._build_anchor(arg, current, flags)
        if op is sre_constants.BRANCH:
            target = self._nfa.new_state()
            for alternative in arg[1]:
                branch_start = self._nfa.new_state()
                self._nfa.add_epsilon(current, branch_start)
                branch_end = self.build_sequence(alternative, branch_start, flags)
                self._nfa.add_epsilon(branch_end, target)
            return target
        if op is sre_constants.SUBPATTERN:
            _, add_flags, del_flags, sub = arg
            return self.build_sequence(sub, current, (flags | add_flags) & ~del_flags)
        if name == "ATOMIC_GROUP":
            return self.build_sequence(arg, current, flags)
        if name in {"MAX_REPEAT", "MIN_REPEAT", "POSSESSIVE_REPEAT"}:
            return self._build_repeat(arg, current, flags)
        if op in {sre_constants.ASSERT, sre_constants.ASSERT_NOT}:
            # Approximation: lookarounds are assumed to succeed.
            return current
        raise _UnsupportedPatternError(f"Unsupported regex construct {name}")

    def _build_anchor(self, anchor: Any, current: int, flags: int) -> int:
        multiline = bool(flags & re.MULTILINE)
        kind: _Anchor | None
        if anchor is sre_constants.AT_BEGINNING:
            kind = _Anchor.BEGIN_LINE if multiline else _Anchor.BEGIN
        elif anchor is sre_constants.AT_BEGINNING_STRING:
            kind = _Anchor.BEGIN
        elif anchor is sre_constants.AT_END:
            kind = _Anchor.END_LINE if multiline else _Anchor.END
        elif anchor is sre_constants.AT_END_STRING:
            kind = _Anchor.END_STRING
        else:
            # Approximation: word boundaries are assumed to hold.
            kind = None
        target = self._nfa.new_state()
        self._nfa.add_epsilon(current, target, kind)
        return target

    def _build_repeat(self, arg: Any, current: int, flags: int) -> int:
        minimum, maximum, sub = arg
        if minimum > MAX_UNROLLED_REPEAT:
            raise _UnsupportedPatternError("Repeat is too large")
        for _ in range(minimum):
            current = self.build_sequence(sub, current, flags)
        if maximum == sre_constants.MAXREPEAT or maximum - minimum > MAX_UNROLLED_REPEAT:
            loop_start = self._nfa.new_state()
            self._nfa.add_epsilon(current, loop_start)
            loop_end = self.build_sequence(sub, loop_start, flags)
            self._nfa.add_epsilon(loop_end, loop_start)
            return loop_start
        target = self._nfa.new_state()
        for _ in range(maximum - minimum):
            self._nfa.add_epsilon(current, target)
            current = self.build_sequence(sub, current, flags)
        self._nfa.add_epsilon(current, target)
        return target


@functools.lru_cache(maxsize=256)
def _compile_nfa(pattern: str, flags: int) -> _Nfa | None:
    try:
        parsed = sre_parse.parse(pattern, flags)
        nfa = _Nfa()
        builder = _NfaBuilder(nfa)
        nfa.accept = builder.build_sequence(parsed, nfa.start, parsed.state.flags)
    except (_UnsupportedPatternError, re.error, RecursionError, ValueError, TypeError):
        return None
    return nfa


def _anchor_holds(anchor: _Anchor | None, string: str, position: int) -> bool:
    length = len(string)
    match anchor:
        case None:
            return True
        case _Anchor.BEGIN:
            return position == 0
        case _Anchor.BEGIN_LINE:
            return position == 0 or string[position - 1] == "\n"
        case _Anchor.END:
            return position == length or (position == length - 1 and string[position] == "\n")
        case _Anchor.END_LINE:
            return position == length or string[position] == "\n"
        case _Anchor.END_STRING:
            return position == length


def _close(nfa: _Nfa, column: list[float], string: str, position: int) -> None:
    """Relax epsilon (cost 0) and insertion (cost 1) transitions within a column.

    This is a 0-1 breadth-first search over the NFA states.
    """
    queue: deque[int] = deque(
        sorted(
            (state for state, cost in enumerate(column) if cost != float("inf")),
            key=column.__getitem__,
        )
    )
    while queue:
        state = queue.popleft()
        cost = column[state]
        for target, anchor in nfa.states[state].epsilons:
            if cost < column[target] and _anchor_holds(anchor, string, position):
                column[target] = cost
                queue.appendleft(target)
        for _, target in nfa.states[state].chars:
            if cost + 1 < column[target]:
                column[target] = cost + 1
                queue.append(target)


def _edit_distance(nfa: _Nfa, string: str, method: RegexMethod) -> float:
    inf = float("inf")
    size = len(nfa.states)
    column = [inf] * size
    column[nfa.start] = 0.0
    _close(nfa, column, string, 0)
    best = column[nfa.accept] if method is not RegexMethod.FULLMATCH else inf
    for position, char in enumerate(string):
        next_column = [inf] * size
        for state, cost in enumerate(column):
            if cost == inf:
                continue
            # Delete the character.
            next_column[state] = min(next_column[state], cost + 1)
            for predicate, target in nfa.states[state].chars:
                # Consume (cost 0) or substitute (cost 1) the character.
                step = cost if predicate(char) else cost + 1
                next_column[target] = min(next_column[target], step)
        if method is RegexMethod.SEARCH:
            # A search may skip any prefix of the string for free.
            next_column[nfa.start] = 0.0
        column = next_column
        _close(nfa, column, string, position + 1)
        if method is not RegexMethod.FULLMATCH:
            # A match or search may ignore the remaining suffix.
            best = min(best, column[nfa.accept])
    if method is RegexMethod.FULLMATCH:
        best = column[nfa.accept]
    return best


def regex_distance(
    pattern: str,
    flags: int,
    method: RegexMethod,
    string: str,
) -> float | None:
    """Compute the edit distance from a string to the language of a regex.

    Args:
        pattern: The source of the regular expression.
        flags: The flags of the compiled pattern.
        method: Whether ``match``, ``search`` or ``fullmatch`` semantics apply.
        string: The string the regex was applied to.

    Returns:
        The minimum number of edits that make the string match, or ``None`` if the
        distance cannot be computed (unsupported pattern, too long string, bytes).
    """
    if not isinstance(pattern, str) or not isinstance(string, str):
        return None
    if len(string) > MAX_STRING_LENGTH:
        return None
    nfa = _compile_nfa(pattern, flags)
    if nfa is None:
        return None
    distance = _edit_distance(nfa, string, method)
    if distance == float("inf"):
        return None
    return distance
