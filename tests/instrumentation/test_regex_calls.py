#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import importlib
import re
from typing import TYPE_CHECKING

import pytest
from bytecode import Bytecode

from pynguin.instrumentation import controlflow as cf
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
    assert call == RegexCall(PATTERN, RegexMethod.SEARCH, "12")
    assert call.matches()


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


def test_regex_distance_only_for_next_predicate(regex_module, subject_properties):
    _, true_distances, false_distances = _distances(
        subject_properties, regex_module.check_later, "zzz", 1
    )
    # The first predicate after the call ("flag is None") consumes the regex outcome,
    # so the later "match is None" check keeps its 0/1 distances.
    assert sorted([*true_distances.values(), *false_distances.values()]) == [0.0, 0.0, 1.0, 1.0]
