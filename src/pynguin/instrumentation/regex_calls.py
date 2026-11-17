#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Finds and records calls of ``re`` matching functions in the subject under test.

Calls like ``PATTERN.match(s)`` or ``re.fullmatch(p, s)`` are executed by the
uninstrumented ``_sre`` engine. To still obtain a gradient for the search, the
instrumentation inserts hooks at such call sites:

* one hook before the attribute load of ``match``/``search``/``fullmatch`` that copies
  the receiver (a compiled pattern or the ``re`` module), and
* one hook after each positional argument has been evaluated that copies it.

The callee itself is never read from the stack, because the call protocol puts a
``NULL`` sentinel next to it in a version-dependent position. Whether the call really
is a regex call is decided at runtime from the receiver. The original call is left
untouched, so the behaviour of the subject does not change.
"""

from __future__ import annotations

import itertools
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from bytecode.instr import BITFLAG2_OPCODES, BITFLAG_OPCODES, Instr

from pynguin.utils.regex_distance import RegexMethod

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pynguin.instrumentation import controlflow as cf

REGEX_METHOD_NAMES: frozenset[str] = frozenset(method.value for method in RegexMethod)

# Pattern methods accept (string, pos, endpos), module functions (pattern, string, flags).
MAX_REGEX_CALL_ARGUMENTS = 3

_CALL_NAMES: frozenset[str] = frozenset({"CALL_METHOD", "CALL_FUNCTION", "PRECALL", "CALL"})

_SITE_IDS = itertools.count()


@dataclass(frozen=True)
class RegexCallSite:
    """A potential regex call site inside a basic block.

    Attributes:
        method_name: The name of the called method (match, search or fullmatch).
        argc: The number of positional arguments of the call.
        load_index: The block index of the method load; the receiver hook goes before it.
        argument_hooks: For each argument, the block index of the instruction after
            which the argument is completely evaluated, and its depth on the stack
            at that point (1 = top of stack, 2 = second element).
        site_id: A unique identifier of the call site.
    """

    method_name: str
    argc: int
    load_index: int
    argument_hooks: tuple[tuple[int, int], ...]
    site_id: int


def _loaded_method_name(instr: Instr) -> tuple[str, int] | None:
    """Extract the attribute name of a method or attribute load.

    Args:
        instr: The instruction.

    Returns:
        The attribute name and the number of stack slots the load leaves for the
        call (2 for a method load, which pushes the callable and self or NULL, and 1
        for a plain attribute load), or None if the instruction is no such load.
    """
    if instr.name == "LOAD_METHOD" and isinstance(instr.arg, str):
        return instr.arg, 2
    if instr.name == "LOAD_ATTR":
        if isinstance(instr.arg, str):
            return instr.arg, 1
        if isinstance(instr.arg, tuple) and isinstance(instr.arg[1], str):
            return instr.arg[1], 2 if instr.arg[0] else 1
    return None


def _pops_and_pushes(instr: Instr) -> tuple[int, int]:
    # Imported lazily, because the version modules import this module.
    from pynguin.instrumentation.version import stack_effects  # noqa: PLC0415

    arg: int | None
    if not instr.require_arg():
        arg = None
    elif isinstance(instr.arg, tuple) and (
        instr.opcode in BITFLAG_OPCODES or instr.opcode in BITFLAG2_OPCODES
    ):
        arg = instr.arg[0] if isinstance(instr.arg[0], int) else None
    elif not isinstance(instr.arg, int):
        arg = 0
    else:
        arg = instr.arg
    effects = stack_effects(instr.opcode, arg, jump=False)
    return effects.pops, effects.pushes


def _argument_hooks(
    last_push: dict[int, tuple[int, int]], callable_slots: int, argc: int
) -> list[tuple[int, int]] | None:
    hooks = []
    for slot in range(callable_slots + 1, callable_slots + argc + 1):
        index, depth_after = last_push[slot]
        stack_position = depth_after - slot + 1
        if stack_position not in {1, 2}:
            return None
        hooks.append((index, stack_position))
    return hooks


def _match_call(
    instructions: Sequence[tuple[int, Instr]], start: int, callable_slots: int
) -> tuple[int, list[tuple[int, int]]] | None:
    """Find the call that consumes the method loaded at ``instructions[start]``.

    Args:
        instructions: The original instructions of the block with their block indices.
        start: The position of the method load in ``instructions``.
        callable_slots: The number of stack slots that the load leaves for the call.

    Returns:
        The number of arguments and, for each argument, the block index and stack depth
        after which the argument is completely evaluated; None if the call cannot be
        handled.
    """
    # Number of stack slots above the receiver's base, i.e., callable (+ self or NULL)
    # + args.
    depth = callable_slots
    # For each stack slot above the callable slots: (block index, depth after instr).
    last_push: dict[int, tuple[int, int]] = {}
    previous_name = ""
    for position, (block_index, instr) in enumerate(instructions[start + 1 :]):
        if position == 0 and callable_slots == 1 and instr.name == "PUSH_NULL":
            # Since 3.13, NULL is pushed after the callable of a plain attribute call.
            callable_slots = depth = 2
            previous_name = instr.name
            continue
        if (
            instr.name in _CALL_NAMES
            and isinstance(instr.arg, int)
            and instr.arg == depth - callable_slots
        ):
            argc = instr.arg
            if previous_name == "KW_NAMES" or not 0 < argc <= MAX_REGEX_CALL_ARGUMENTS:
                # Keyword arguments (3.11, 3.12) or unsupported arity.
                return None
            hooks = _argument_hooks(last_push, callable_slots, argc)
            return None if hooks is None else (argc, hooks)
        try:
            pops, pushes = _pops_and_pushes(instr)
        except (AssertionError, ValueError, KeyError, TypeError):
            return None
        lowest = depth - pops
        if lowest < callable_slots:
            # The callable was consumed by something other than the expected call.
            return None
        depth = lowest + pushes
        for slot in range(lowest + 1, depth + 1):
            last_push[slot] = (block_index, depth)
        # Slots above the current depth are no longer valid.
        for slot in [slot for slot in last_push if slot > depth]:
            del last_push[slot]
        previous_name = instr.name
    return None


def find_regex_call_sites(node: cf.BasicBlockNode) -> list[RegexCallSite]:
    """Find potential regex call sites within a basic block.

    A potential site is a method load named ``match``, ``search`` or ``fullmatch``
    whose call uses only positional arguments and lies in the same basic block.

    Args:
        node: The basic block node.

    Returns:
        The call sites in the block.
    """
    instructions = list(node.instrumentation_original_instructions)
    sites: list[RegexCallSite] = []
    for position, (block_index, instr) in enumerate(instructions):
        loaded = _loaded_method_name(instr)
        if loaded is None or loaded[0] not in REGEX_METHOD_NAMES:
            continue
        method_name, callable_slots = loaded
        matched = _match_call(instructions, position, callable_slots)
        if matched is None:
            continue
        argc, hooks = matched
        sites.append(
            RegexCallSite(
                method_name=method_name,
                argc=argc,
                load_index=block_index,
                argument_hooks=tuple(hooks),
                site_id=next(_SITE_IDS),
            )
        )
    return sites


@dataclass(frozen=True)
class RegexCall:
    """A call of a regex matching function observed at runtime."""

    pattern: re.Pattern[str]
    method: RegexMethod
    string: str

    def matches(self) -> bool:
        """Check whether the call finds a match.

        Returns:
            True, if the regex call returns a match object.
        """
        return getattr(self.pattern, self.method.value)(self.string) is not None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _interpret_call(method_name: str, receiver: Any, args: Sequence[Any]) -> RegexCall | None:
    method = RegexMethod(method_name)
    if isinstance(receiver, re.Pattern):
        string = args[0]
        if not isinstance(receiver.pattern, str) or not isinstance(string, str):
            return None
        pos = _as_int(args[1]) if len(args) > 1 else 0
        endpos = _as_int(args[2]) if len(args) > 2 else len(string)
        if pos is None or endpos is None:
            return None
        return RegexCall(receiver, method, string[pos:endpos])
    if receiver is re and len(args) >= 2:
        pattern, string = args[0], args[1]
        flags = args[2] if len(args) > 2 else 0
        if not isinstance(string, str) or not isinstance(flags, int):
            return None
        if isinstance(pattern, re.Pattern):
            if flags != 0 or not isinstance(pattern.pattern, str):
                return None
            return RegexCall(pattern, method, string)
        if not isinstance(pattern, str):
            return None
        try:
            return RegexCall(re.compile(pattern, flags), method, string)
        except (re.error, ValueError, TypeError, OverflowError):
            return None
    return None


class RegexCallCollector:
    """Collects the receiver and arguments of regex call sites at runtime.

    The collector is not thread-safe; owners keep one collector per thread.
    """

    def __init__(self) -> None:  # noqa: D107
        self._parts: dict[int, list[Any]] = {}

    def add_part(
        self,
        value: Any,
        site_id: int,
        index: int,
        argc: int,
        method_name: str,
    ) -> RegexCall | None:
        """Record a receiver (index 0) or an argument (index >= 1) of a call site.

        Args:
            value: The receiver or argument value.
            site_id: The call site identifier.
            index: 0 for the receiver, otherwise the 1-based argument position.
            argc: The number of positional arguments of the call.
            method_name: The name of the called method.

        Returns:
            The regex call once the last argument was recorded and the call is a
            regex call, otherwise None.
        """
        parts = self._parts
        if index == 0:
            parts[site_id] = [value]
            return None
        collected = parts.get(site_id)
        if collected is None or len(collected) != index:
            # Out of order, e.g., because of an exception in a previous evaluation.
            parts.pop(site_id, None)
            return None
        collected.append(value)
        if index < argc:
            return None
        del parts[site_id]
        try:
            return _interpret_call(method_name, collected[0], collected[1:])
        except Exception:  # noqa: BLE001
            return None

    def reset(self) -> None:
        """Forget all partially recorded calls."""
        self._parts = {}
