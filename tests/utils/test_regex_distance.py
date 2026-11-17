#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import random
import re

import pytest

from pynguin.utils import regex_distance as rd
from pynguin.utils.regex_distance import RegexMethod, regex_distance


@pytest.mark.parametrize(
    "pattern,flags,method,string,expected",
    [
        (r"abc", 0, RegexMethod.FULLMATCH, "abc", 0.0),
        (r"abc", 0, RegexMethod.FULLMATCH, "abd", 1.0),
        (r"abc", 0, RegexMethod.FULLMATCH, "", 3.0),
        (r"abc", 0, RegexMethod.FULLMATCH, "abcd", 1.0),
        (r"abc", 0, RegexMethod.MATCH, "abcd", 0.0),
        (r"abc", 0, RegexMethod.MATCH, "xabc", 1.0),
        (r"abc", 0, RegexMethod.SEARCH, "xxabcxx", 0.0),
        (r"abc", 0, RegexMethod.SEARCH, "xxabxx", 1.0),
        (r"^\d+\.\d+\.\d+$", 0, RegexMethod.MATCH, "1.2.x", 1.0),
        (r"^\d+\.\d+\.\d+$", 0, RegexMethod.MATCH, "zzz", 5.0),
        (r"^\d+\.\d+\.\d+$", 0, RegexMethod.MATCH, "1.2.3\n", 0.0),
        (r"#[0-9a-f]{6}", 0, RegexMethod.FULLMATCH, "#12", 4.0),
        (r"#[0-9a-f]{6}", re.IGNORECASE, RegexMethod.FULLMATCH, "#ABCDEF", 0.0),
        (r"#[0-9a-f]{6}", 0, RegexMethod.FULLMATCH, "#ABCDEF", 6.0),
        (r"(?i)ab|cd", 0, RegexMethod.FULLMATCH, "CD", 0.0),
        (r"a{2,4}", 0, RegexMethod.FULLMATCH, "aaaaaa", 2.0),
        (r"a{2,}", 0, RegexMethod.FULLMATCH, "a", 1.0),
        (r"a*?b+?", 0, RegexMethod.FULLMATCH, "aac", 1.0),
        (r"[^abc]x?", 0, RegexMethod.FULLMATCH, "a", 1.0),
        (r"\s\S\w\W\D", 0, RegexMethod.FULLMATCH, " a_!x", 0.0),
        (r"\d", re.ASCII, RegexMethod.FULLMATCH, "٣", 1.0),
        (r"a.c", 0, RegexMethod.FULLMATCH, "a\nc", 1.0),
        (r"a.c", re.DOTALL, RegexMethod.FULLMATCH, "a\nc", 0.0),
        (r"(?m)^ab$", 0, RegexMethod.SEARCH, "x\nab\ny", 0.0),
        (r"\Aab\Z", 0, RegexMethod.SEARCH, "xab", 1.0),
        (r"[^a]", re.IGNORECASE, RegexMethod.FULLMATCH, "A", 1.0),
        (r"[a-c]", re.IGNORECASE, RegexMethod.FULLMATCH, "B", 0.0),
        (r"\bfoo(?=x)", 0, RegexMethod.SEARCH, "fo", 1.0),
        (r"(?:ab){2}", 0, RegexMethod.FULLMATCH, "abab", 0.0),
    ],
)
def test_regex_distance(pattern, flags, method, string, expected):
    assert regex_distance(pattern, flags, method, string) == expected


@pytest.mark.parametrize(
    "pattern,string",
    [
        (r"(a)\1", "aa"),
        (r"(?P<x>a)(?(x)b|c)", "ab"),
        ("a{100}", "a"),
        ("[", "a"),
        ("a", "a" * (rd.MAX_STRING_LENGTH + 1)),
        (b"a", "a"),
        ("a", b"a"),
    ],
)
def test_regex_distance_unsupported(pattern, string):
    assert regex_distance(pattern, 0, RegexMethod.SEARCH, string) is None


def test_regex_distance_too_many_states(monkeypatch):
    rd._compile_nfa.cache_clear()
    monkeypatch.setattr(rd, "MAX_NFA_STATES", 3)
    try:
        assert regex_distance("abcdef", 0, RegexMethod.FULLMATCH, "abc") is None
    finally:
        rd._compile_nfa.cache_clear()


def test_regex_distance_large_bounded_repeat():
    assert regex_distance("a{0,40}b", 0, RegexMethod.FULLMATCH, "aab") == 0.0
    assert regex_distance("a{0,40}b", 0, RegexMethod.FULLMATCH, "aa") == 1.0


def test_regex_distance_linebreak_category():
    nfa = rd._Nfa()
    predicate = rd._category_predicate("CATEGORY_LINEBREAK", ascii_only=False)
    assert predicate("\n")
    assert not predicate("a")
    assert nfa.accept == nfa.start


def test_regex_distance_unknown_category():
    with pytest.raises(rd._UnsupportedPatternError):
        rd._category_predicate("CATEGORY_LOC_WORD_X", ascii_only=False)


@pytest.mark.parametrize(
    "pattern",
    [
        r"^\d+\.\d+\.\d+$",
        r"#[0-9a-f]{6}",
        r"(?i)ab|cd",
        r"a{2,4}b*",
        r"^\s*$",
        r"[^abc]+x?",
        r"(?m)^ab$",
        r"a.c",
        r"(?s)a.c",
        r"[\w.+-]+@[\w-]+\.[a-z]{2,}",
        r"a*?b+?",
    ],
)
def test_distance_is_zero_iff_match(pattern):
    compiled = re.compile(pattern)
    rng = random.Random(42)  # noqa: S311
    alphabet = "ab#c0f1.9 \nxyz@A"
    for _ in range(200):
        string = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8)))
        for method in RegexMethod:
            matched = getattr(compiled, method.value)(string) is not None
            distance = regex_distance(compiled.pattern, compiled.flags, method, string)
            assert distance is not None
            assert (distance == 0.0) == matched, (pattern, method, string)
