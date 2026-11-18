#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import importlib
import re
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest import mock

import pytest
from bytecode import Bytecode

from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation import regex_calls
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.regex_calls import (
    RegexCall,
    RegexCallCollector,
    find_regex_call_sites,
)
from pynguin.utils.regex_distance import RegexMethod

if TYPE_CHECKING:
    from pynguin.instrumentation.tracer import SubjectProperties

PATTERN = re.compile(r"\d+")


def _sites(source: str) -> list[tuple[str, int]]:
    namespace: dict = {}
    exec(compile(source, "<test>", "exec"), namespace)  # noqa: S102
    cfg = cf.CFG.from_bytecode(Bytecode.from_code(namespace["f"].__code__))
    return [
        (site.method_name, site.argc)
        for node in cfg.basic_block_nodes
        for site in find_regex_call_sites(node)
    ]


@pytest.mark.parametrize(
    "body,expected",
    [
        ("return R.match(s)", [("match", 1)]),
        ("return R.search(s, 2)", [("search", 2)]),
        ("return R.fullmatch(s, 1, 3)", [("fullmatch", 3)]),
        ("return re.match(p, s)", [("match", 2)]),
        ("return re.fullmatch(p, s.strip(), re.I)", [("fullmatch", 3)]),
        ("return R.match(R.search(s))", [("match", 1), ("search", 1)]),
        ("return R.match(s, pos=1)", []),
        ("return R.match(*s)", []),
        ("return R.match()", []),
        ("return R.match(s, 1, 2, 3)", []),
        ("return R.sub(s, s)", []),
        ("f = R.match\n    return f(s)", []),
        ("return R.match(s if p else s)", []),
    ],
)
def test_find_regex_call_sites(body, expected):
    source = f"def f(R, re, p, s):\n    {body}\n"
    assert sorted(_sites(source)) == sorted(expected)


def test_find_regex_call_sites_unique_ids():
    namespace: dict = {}
    exec(  # noqa: S102
        compile("def f(R, s):\n    return R.match(s) or R.search(s)\n", "<test>", "exec"),
        namespace,
    )
    cfg = cf.CFG.from_bytecode(Bytecode.from_code(namespace["f"].__code__))
    ids = [site.site_id for node in cfg.basic_block_nodes for site in find_regex_call_sites(node)]
    assert len(ids) == len(set(ids)) == 2


def _collect(collector: RegexCallCollector, method: str, receiver, *args) -> RegexCall | None:
    result = collector.add_part(receiver, 7, 0, len(args), method)
    assert result is None
    for index, arg in enumerate(args, start=1):
        result = collector.add_part(arg, 7, index, len(args), method)
    return result


def test_collector_pattern_method():
    call = _collect(RegexCallCollector(), "match", PATTERN, "ab12")
    assert call == RegexCall(PATTERN, RegexMethod.MATCH, "ab12")
    assert not call.matches()


def test_collector_pattern_method_pos_endpos():
    call = _collect(RegexCallCollector(), "search", PATTERN, "ab12cd", 2, 4)
    assert call == RegexCall(PATTERN, RegexMethod.SEARCH, "ab12cd", 2, 4)
    assert call.matches()


@pytest.mark.parametrize(
    "pattern,string,pos,endpos",
    [
        # "^" does not hold at pos > 0, so slicing would wrongly report a match.
        (r"^\d", "a1", 1, None),
        (r"^x$", "xx", 1, 2),
        # A negative pos is treated as 0 by re, not as an index from the end.
        (r"a", "ab", -1, None),
        (r"b$", "ab", 0, -5),
    ],
)
def test_regex_call_pos_endpos_semantics(pattern, string, pos, endpos):
    compiled = re.compile(pattern)
    args = (string, pos) if endpos is None else (string, pos, endpos)
    call = _collect(RegexCallCollector(), "search", compiled, *args)
    assert call is not None
    expected = compiled.search(*args) is not None
    assert call.matches() == expected
    distance = call.distance()
    # None: no edit of the searched part can make "^" hold at pos > 0.
    assert (distance == 0) == expected


def test_collector_module_function():
    call = _collect(RegexCallCollector(), "fullmatch", re, "a+", "AA", re.IGNORECASE)
    assert call is not None
    assert call.pattern.pattern == "a+"
    assert call.pattern.flags & re.IGNORECASE
    assert call.matches()


def test_collector_module_function_compiled_pattern():
    call = _collect(RegexCallCollector(), "match", re, PATTERN, "1")
    assert call == RegexCall(PATTERN, RegexMethod.MATCH, "1")


@pytest.mark.parametrize(
    "receiver,args",
    [
        (object(), ("a",)),
        (PATTERN, (1,)),
        (PATTERN, ("a", "x")),
        (PATTERN, ("a", 0, "x")),
        (re.compile(rb"a"), (b"a",)),
        (re, ("a",)),
        (re, ("a", 1)),
        (re, ("a", "a", "x")),
        (re, (PATTERN, "a", re.IGNORECASE)),
        (re, (re.compile(rb"a"), "a")),
        (re, (1, "a")),
        (re, ("[", "a")),
    ],
)
def test_collector_ignores_non_regex_calls(receiver, args):
    assert _collect(RegexCallCollector(), "match", receiver, *args) is None


def test_collector_out_of_order():
    collector = RegexCallCollector()
    assert collector.add_part("s", 1, 1, 1, "match") is None
    collector.add_part(PATTERN, 1, 0, 2, "match")
    assert collector.add_part("s", 1, 2, 2, "match") is None
    # The out-of-order part discarded the site.
    assert collector.add_part("s", 1, 1, 2, "match") is None


def test_collector_reset():
    collector = RegexCallCollector()
    collector.add_part(PATTERN, 1, 0, 1, "match")
    collector.reset()
    assert collector.add_part("1", 1, 1, 1, "match") is None


@pytest.fixture
def regex_module(subject_properties: SubjectProperties):
    name = "tests.fixtures.regex.regex_checks"
    with install_import_hook(name, subject_properties), subject_properties.instrumentation_tracer:
        return importlib.reload(importlib.import_module(name))


def _distances(subject_properties: SubjectProperties, function, *args):
    tracer = subject_properties.instrumentation_tracer
    tracer.tracer.init_trace()
    with tracer:
        result = function(*args)
    trace = tracer.get_trace()
    return result, dict(trace.true_distances), dict(trace.false_distances)


def test_regex_distance_for_is_none_check(regex_module, subject_properties):
    result, true_distances, false_distances = _distances(
        subject_properties, regex_module.bump, "zzz"
    )
    assert result == "invalid"
    # Depending on the Python version, the check is "is None" or "is not None"; the
    # side that is taken has distance 0, reaching a match needs 5 edits.
    assert sorted([*true_distances.values(), *false_distances.values()]) == [0.0, 5.0]


def test_regex_distance_for_truthiness_check(regex_module, subject_properties):
    result, true_distances, _ = _distances(subject_properties, regex_module.is_hex_color, "#12")
    assert result is False
    assert list(true_distances.values()) == [4.0]


def test_regex_distance_for_matching_string(regex_module, subject_properties):
    result, true_distances, _ = _distances(subject_properties, regex_module.is_hex_color, "#12ab34")
    assert result is True
    assert list(true_distances.values()) == [0.0]


def test_regex_distance_not_for_other_match_methods(regex_module, subject_properties):
    result, true_distances, _ = _distances(
        subject_properties, regex_module.not_a_regex, regex_module.Matcher(), "a"
    )
    assert result is True
    assert list(true_distances.values()) == [0.0]


@pytest.mark.parametrize("flag", [1, None])
def test_regex_distance_only_for_predicate_testing_result(regex_module, subject_properties, flag):
    _, true_distances, false_distances = _distances(
        subject_properties, regex_module.check_later, "zzz", flag
    )
    # Only "match is None" tests the result; the "flag is None" check in between
    # keeps its 0/1 distances, even if flag is None.
    assert sorted([*true_distances.values(), *false_distances.values()]) == [0.0, 0.0, 1.0, 5.0]
    lines = {
        meta.line_no: predicate
        for predicate, meta in subject_properties.existing_predicates.items()
        if predicate in true_distances
    }
    match_predicate = lines[max(lines)]
    assert 5.0 in {true_distances[match_predicate], false_distances[match_predicate]}


def test_regex_distance_for_walrus(regex_module, subject_properties):
    result, true_distances, false_distances = _distances(
        subject_properties, regex_module.walrus, "1.2.x"
    )
    assert result is False
    assert 1.0 in {*true_distances.values(), *false_distances.values()}


def test_regex_call_without_testing_predicate_not_instrumented(regex_module, subject_properties):
    tracer = subject_properties.instrumentation_tracer
    with mock.patch.object(type(tracer.tracer), "executed_regex_call_part") as hook:
        _distances(subject_properties, regex_module.untested, "zzz")
    hook.assert_not_called()


@pytest.mark.parametrize(
    "instr,before,after",
    [
        (SimpleNamespace(name="DUP_TOP", arg=None), [{1}], [{1}, {1}]),
        (SimpleNamespace(name="COPY", arg=2), [{1}, {2}], [{1}, {2}, {1}]),
        (SimpleNamespace(name="COPY", arg=3), [{1}], [{1}, set()]),
        (SimpleNamespace(name="SWAP", arg=2), [{1}, {2}], [{2}, {1}]),
        (SimpleNamespace(name="ROT_TWO", arg=None), [{1}, {2}], [{2}, {1}]),
    ],
)
def test_move_stack_entries(instr, before, after):
    stack = [frozenset(entry) for entry in before]
    assert regex_calls._move_stack_entries(instr, stack)
    assert stack == [frozenset(entry) for entry in after]


def test_move_stack_entries_other_instruction():
    assert not regex_calls._move_stack_entries(SimpleNamespace(name="POP_TOP", arg=None), [])


@pytest.mark.parametrize(
    "names,expected",
    [
        ([("STORE_FAST", "m")], "m"),
        ([("DUP_TOP", None), ("STORE_FAST", "m")], "m"),
        ([("COPY", 1), ("STORE_NAME", "m")], "m"),
        ([("COPY", 2), ("STORE_FAST", "m")], None),
        ([("STORE_FAST_LOAD_FAST", ("m", "m"))], "m"),
        ([("STORE_DEREF", SimpleNamespace(name="m"))], "m"),
        ([("POP_TOP", None)], None),
        ([("DUP_TOP", None)], None),
        ([], None),
    ],
)
def test_stored_variable(names, expected):
    instructions = [
        (index, SimpleNamespace(name=name, arg=arg)) for index, (name, arg) in enumerate(names)
    ]
    assert regex_calls._stored_variable(instructions, 0) == expected


@pytest.mark.parametrize(
    "name,arg,expected",
    [
        ("LOAD_FAST", "m", ["m"]),
        ("LOAD_FAST_LOAD_FAST", ("a", "b"), ["a", "b"]),
        ("LOAD_DEREF", SimpleNamespace(name="m"), ["m"]),
        ("STORE_FAST_LOAD_FAST", ("a", "b"), ["b"]),
        ("LOAD_CONST", 1, None),
    ],
)
def test_loaded_variables(name, arg, expected):
    assert regex_calls._loaded_variables(SimpleNamespace(name=name, arg=arg)) == expected
