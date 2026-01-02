#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for the string subtype inference."""

import re

import pytest

from pynguin.analyses import string_subtypes
from pynguin.analyses.string_subtypes import generate_from_regex, infer_regex_from_methods
from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def empty_methods():
    """Fixture for an empty methods dictionary."""
    return {}


def test_infer_regex_empty(empty_methods):
    regex = infer_regex_from_methods(empty_methods)
    assert regex.pattern == ".*"
    assert regex.search("anything")


def test_infer_regex_startswith():
    regex = infer_regex_from_methods({"startswith": OrderedSet(["abc"])})
    assert regex.search("abcde")
    assert not regex.search("deabc")


def test_infer_regex_endswith():
    regex = infer_regex_from_methods({"endswith": OrderedSet(["xyz"])})
    assert regex.search("hello_xyz")
    assert not regex.search("xyz_hello")


def test_infer_regex_split():
    regex = infer_regex_from_methods({"split": OrderedSet([","])})
    assert regex.fullmatch("a,b,c")
    assert regex.fullmatch("a")
    assert not regex.fullmatch("a,b,")  # trailing comma not allowed


def test_infer_regex_partition():
    regex = infer_regex_from_methods({"partition": OrderedSet([":"])})
    assert regex.search("abc:def")
    assert regex.search("def:ghi")
    assert not regex.search("abcdef")


def test_infer_regex_find_and_index():
    regex = infer_regex_from_methods({"find": OrderedSet(["foo"]), "index": OrderedSet(["bar"])})
    assert regex.search("xxfooxxbarxx")
    assert not regex.search("xxbazxx")


def test_infer_regex_replace():
    regex = infer_regex_from_methods({"replace": ["a", "b"]})
    assert regex.search("abc")
    assert regex.search("bbc")
    assert not regex.search("ccc")


def test_infer_regex_strip():
    regex = infer_regex_from_methods({"strip": OrderedSet()})
    assert regex.search("   hello   ")


def test_infer_regex_zfill():
    regex = infer_regex_from_methods({"zfill": OrderedSet([3])})
    assert regex.search("007")
    assert regex.search("123")
    assert regex.search("12345")


def test_infer_regex_center_and_just():
    regex = infer_regex_from_methods({"center": OrderedSet([5]), "ljust": OrderedSet([3])})
    assert regex.search("hi")
    assert regex.search("abc")
    assert regex.search("abcde")


def test_infer_regex_remove_prefix_suffix():
    regex = infer_regex_from_methods({
        "removeprefix": OrderedSet(["pre"]),
        "removesuffix": OrderedSet(["suf"]),
    })
    assert regex.search("presufsuf")
    assert regex.search("prebody")
    assert regex.search("bodysuf")


def test_infer_regex_translate_count_splitlines_format():
    regex = infer_regex_from_methods({
        "translate": OrderedSet(),
        "count": OrderedSet(["x"]),
        "splitlines": OrderedSet(),
        "format": OrderedSet(),
    })
    assert regex.search("hello\nworld")
    assert regex.search("abc")
    assert not regex.search("")


def test_generate_from_valid_regex():
    regex = re.compile(r"[a-z]{3}")
    s = generate_from_regex(regex)
    assert isinstance(s, str)
    assert regex.fullmatch(s)


def test_generate_from_invalid_regex(monkeypatch):
    # Force rstr.xeger to raise
    def boom(_):
        raise ValueError("bad regex")

    monkeypatch.setattr(string_subtypes.STRING_GENERATOR, "xeger", boom)

    regex = re.compile(r".*")
    s = generate_from_regex(regex)
    assert not s
