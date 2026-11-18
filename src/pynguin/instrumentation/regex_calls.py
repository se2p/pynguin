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

from pynguin.utils.regex_distance import RegexMethod, regex_distance

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
        result_index: The block index of the instruction that pushes the call's result.
        result_variable: The name of the variable the result is directly stored to,
            e.g., ``m`` in ``m = PATTERN.match(s)``; None if it is not stored.
    """

    method_name: str
    argc: int
    load_index: int
    argument_hooks: tuple[tuple[int, int], ...]
    site_id: int
    result_index: int = -1
    result_variable: str | None = None


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
) -> tuple[int, list[tuple[int, int]], int] | None:
    """Find the call that consumes the method loaded at ``instructions[start]``.

    Args:
        instructions: The original instructions of the block with their block indices.
        start: The position of the method load in ``instructions``.
        callable_slots: The number of stack slots that the load leaves for the call.

    Returns:
        The number of arguments, for each argument the block index and stack depth
        after which the argument is completely evaluated, and the position of the call
        instruction in ``instructions``; None if the call cannot be handled.
    """
    # Number of stack slots above the receiver's base, i.e., callable (+ self or NULL)
    # + args.
    depth = callable_slots
    # For each stack slot above the callable slots: (block index, depth after instr).
    last_push: dict[int, tuple[int, int]] = {}
    previous_name = ""
    for position, (block_index, instr) in enumerate(instructions[start + 1 :], start=start + 1):
        if position == start + 1 and callable_slots == 1 and instr.name == "PUSH_NULL":
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
            return None if hooks is None else (argc, hooks, position)
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
        argc, hooks, call_position = matched
        result_position = call_position
        if instructions[call_position][1].name == "PRECALL":
            # Python 3.11: PRECALL is followed by the CALL that pushes the result.
            result_position += 1
            if result_position >= len(instructions):
                continue
        sites.append(
            RegexCallSite(
                method_name=method_name,
                argc=argc,
                load_index=block_index,
                argument_hooks=tuple(hooks),
                site_id=next(_SITE_IDS),
                result_index=instructions[result_position][0],
                result_variable=_stored_variable(instructions, result_position + 1),
            )
        )
    return sites


_STORE_NAMES = frozenset({"STORE_FAST", "STORE_NAME", "STORE_GLOBAL", "STORE_DEREF"})


def _variable_name(arg: Any) -> str | None:
    if isinstance(arg, str):
        return arg
    # LOAD_DEREF and STORE_DEREF take cell or free variables.
    name = getattr(arg, "name", None)
    return name if isinstance(name, str) else None


def _stored_variable(instructions: Sequence[tuple[int, Instr]], position: int) -> str | None:
    """Get the variable that the value on top of the stack is stored to.

    Handles ``m = call()`` (a store directly after the call), the walrus operator
    (``DUP_TOP`` or ``COPY 1`` before the store) and the superinstructions of 3.13+
    that combine the store with another load or store.

    Args:
        instructions: The original instructions of the block with their block indices.
        position: The position after the instruction that pushed the value.

    Returns:
        The variable name, or None if the value is not directly stored.
    """
    if position < len(instructions):
        instr = instructions[position][1]
        if instr.name == "DUP_TOP" or (instr.name == "COPY" and instr.arg == 1):
            position += 1
    if position >= len(instructions):
        return None
    instr = instructions[position][1]
    if instr.name in _STORE_NAMES:
        return _variable_name(instr.arg)
    if instr.name in {"STORE_FAST_LOAD_FAST", "STORE_FAST_STORE_FAST"} and isinstance(
        instr.arg, tuple
    ):
        return _variable_name(instr.arg[0])
    return None


# Instructions that test their operands; the result inherits the operands' origins.
_TEST_NAMES = frozenset({"COMPARE_OP", "IS_OP", "TO_BOOL", "UNARY_NOT"})


def _loaded_variables(instr: Instr) -> list[str] | None:
    """Get the variables loaded by an instruction, one per pushed value."""
    name = instr.name
    if name.startswith("LOAD_FAST") and isinstance(instr.arg, tuple):
        # 3.13+ superinstructions like LOAD_FAST_LOAD_FAST load two variables.
        names = [_variable_name(arg) for arg in instr.arg]
        return [name for name in names if name is not None]
    if name.startswith("LOAD_FAST") or name in {"LOAD_NAME", "LOAD_DEREF"}:
        variable = _variable_name(instr.arg)
        return None if variable is None else [variable]
    if name == "STORE_FAST_LOAD_FAST" and isinstance(instr.arg, tuple):
        variable = _variable_name(instr.arg[1])
        return None if variable is None else [variable]
    return None


Origins = frozenset[tuple[str, Any]]


def _move_stack_entries(instr: Instr, stack: list[Origins]) -> bool:
    """Simulate an instruction that only copies or reorders stack entries.

    Args:
        instr: The instruction.
        stack: The abstract stack, modified in place.

    Returns:
        True, if the instruction was simulated.
    """
    name = instr.name
    if name == "DUP_TOP" or (name == "COPY" and isinstance(instr.arg, int)):
        depth = 1 if name == "DUP_TOP" else instr.arg
        assert isinstance(depth, int)
        stack.append(stack[-depth] if len(stack) >= depth else frozenset())
        return True
    if name == "SWAP" and isinstance(instr.arg, int) and len(stack) >= instr.arg:
        stack[-1], stack[-instr.arg] = stack[-instr.arg], stack[-1]
        return True
    if name == "ROT_TWO" and len(stack) >= 2:
        stack[-1], stack[-2] = stack[-2], stack[-1]
        return True
    return False


def tested_origins(node: cf.BasicBlockNode, sites: Sequence[RegexCallSite]) -> Origins | None:
    """Find where the value tested by the conditional jump of a basic block comes from.

    The block is simulated on an abstract stack whose entries record their origins:
    ``("site", site_id)`` for the result of a regex call site in the block and
    ``("var", name)`` for a loaded variable. Tests like ``is None``, comparisons and
    ``TO_BOOL`` pass the origins of their operands on.

    Args:
        node: The basic block node.
        sites: The regex call sites in the block.

    Returns:
        The origins of the value tested by the block's conditional jump, or None if the
        block does not end with a conditional jump or cannot be simulated.
    """
    instructions = list(node.instrumentation_original_instructions)
    if not instructions:
        return None
    last = instructions[-1][1]
    if "JUMP" not in last.name or "IF" not in last.name:
        return None
    site_results = {site.result_index: site.site_id for site in sites}
    empty: Origins = frozenset()
    stack: list[Origins] = []

    def pop() -> Origins:
        return stack.pop() if stack else empty

    for block_index, instr in instructions[:-1]:
        if _move_stack_entries(instr, stack):
            continue
        name = instr.name
        try:
            pops, pushes = _pops_and_pushes(instr)
        except (AssertionError, ValueError, KeyError, TypeError):
            return None
        popped = [pop() for _ in range(pops)]
        if block_index in site_results:
            stack.extend([empty] * (pushes - 1))
            stack.append(frozenset({("site", site_results[block_index])}))
            continue
        if name in _TEST_NAMES and pushes == 1:
            stack.append(frozenset().union(*popped))
            continue
        variables = _loaded_variables(instr)
        if variables is not None and len(variables) == pushes:
            stack.extend(frozenset({("var", variable)}) for variable in variables)
            continue
        stack.extend([empty] * pushes)
    return pop()


def is_tested_by(site: RegexCallSite, origins: Origins) -> bool:
    """Check whether a predicate with the given origins tests the result of a site.

    Args:
        site: The regex call site.
        origins: The origins of the value tested by the predicate.

    Returns:
        True, if the predicate tests the call result or the variable it is stored to.
    """
    if ("site", site.site_id) in origins:
        return True
    return site.result_variable is not None and ("var", site.result_variable) in origins


@dataclass(frozen=True)
class RegexCall:
    """A call of a regex matching function observed at runtime.

    Attributes:
        pattern: The compiled pattern.
        method: The called method.
        string: The complete string the pattern is applied to.
        pos: The ``pos`` argument of the call, as passed.
        endpos: The ``endpos`` argument of the call, as passed.
    """

    pattern: re.Pattern[str]
    method: RegexMethod
    string: str
    pos: int = 0
    endpos: int | None = None

    def matches(self) -> bool:
        """Check whether the call finds a match.

        Returns:
            True, if the regex call returns a match object.
        """
        method = getattr(self.pattern, self.method.value)
        endpos = len(self.string) if self.endpos is None else self.endpos
        return method(self.string, self.pos, endpos) is not None

    def distance(self) -> float | None:
        """Compute the edit distance of the searched string to a match.

        Returns:
            The distance, or None if it cannot be computed.
        """
        return regex_distance(
            self.pattern.pattern,
            self.pattern.flags,
            self.method,
            self.string,
            pos=self.pos,
            endpos=self.endpos,
        )


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _interpret_call(method_name: str, receiver: Any, args: Sequence[Any]) -> RegexCall | None:
    method = RegexMethod(method_name)
    if isinstance(receiver, re.Pattern):
        string = args[0]
        if not isinstance(receiver.pattern, str) or not isinstance(string, str):
            return None
        pos = _as_int(args[1]) if len(args) > 1 else 0
        endpos = _as_int(args[2]) if len(args) > 2 else None
        if pos is None or (len(args) > 2 and endpos is None):
            return None
        return RegexCall(receiver, method, string, pos, endpos)
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
