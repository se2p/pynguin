#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import re
from unittest import mock

import pytest

import pynguin.utils.typetracing as tt
from pynguin.analyses.constants import (
    ConstantPool,
    DelegatingConstantProvider,
    DynamicConstantProvider,
    EmptyConstantProvider,
    RestrictedConstantPool,
)
from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def pool() -> ConstantPool:
    return ConstantPool()


@pytest.fixture
def rpool() -> ConstantPool:
    return RestrictedConstantPool(max_size=5)


def test_has_constant(pool):
    pool.add_constant(42)
    assert pool.has_constant_for(int)


def test_has_no_constant(pool):
    assert not pool.has_constant_for(int)


def test_get_constant_for(pool):
    pool.add_constant(42)
    assert pool.get_constant_for(int) == 42


def test_add_constant(pool):
    pool.add_constant(42)
    assert pool._constants[int] == OrderedSet([42])


def test_remove_constant(pool):
    pool.add_constant(42)
    pool.add_constant(17)
    assert len(pool) == 2
    pool.remove_constant(17)
    assert len(pool) == 1


def test_get_all_constants(pool):
    pool.add_constant(42)
    pool.add_constant(5)
    assert pool.get_all_constants_for(int) == OrderedSet([42, 5])


def test_empty_provider_has_no_constants():
    assert EmptyConstantProvider().get_all_constants_for(str) == OrderedSet()


def test_delegating_provider_unions_all_constants(pool):
    pool.add_constant("thousand")
    delegate_pool = ConstantPool()
    delegate_pool.add_constant("hundred")
    delegate = DelegatingConstantProvider(delegate_pool, EmptyConstantProvider(), 1.0)
    provider = DelegatingConstantProvider(pool, delegate, 1.0)
    assert provider.get_all_constants_for(str) == OrderedSet(["thousand", "hundred"])


def test_len(pool):
    assert len(pool) == 0


def test_len_not_empty(pool):
    pool.add_constant(42)
    pool.add_constant(13.37)
    assert len(pool) == 2


def test_restriced(rpool):
    for i in range(20):
        rpool.add_constant(i)
    assert rpool.get_all_constants_for(int) == OrderedSet([15, 16, 17, 18, 19])


def test_restriced_str(rpool):
    for i in range(20):
        rpool.add_constant(chr(ord("A") + i))
    assert rpool.get_all_constants_for(str) == OrderedSet(["P", "Q", "R", "S", "T"])


def test_dynamic_constant_pool_max_size(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 5)
    provider.add_value("abcd")
    provider.add_value("abcde")
    provider.add_value("abcdef")
    assert rpool.get_all_constants_for(str) == OrderedSet(["abcd", "abcde"])


def test_constant_pool_ignores_proxy(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 5)
    provider.add_value(tt.ObjectProxy(5))
    assert rpool.get_all_constants_for(int) == OrderedSet([5])


def test_constant_pool_ignores_proxy_2(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 5)
    provider.add_value_for_strings(tt.ObjectProxy("foo"), "isupper")
    assert rpool.get_all_constants_for(str) == OrderedSet(["foo", "FOO"])


def _add_regex_call(provider: DynamicConstantProvider, pattern, string: str) -> None:
    provider.add_regex_call_part(pattern, 1, 0, 1, "fullmatch")
    provider.add_regex_call_part(tt.ObjectProxy(string), 1, 1, 1, "fullmatch")


def test_dynamic_constant_provider_regex_call(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 50)
    _add_regex_call(provider, re.compile(r"[a-c]{3}"), "x")
    seeded = rpool.get_all_constants_for(str)
    assert len(seeded) == 1
    assert re.fullmatch(r"[a-c]{3}", next(iter(seeded)))


def test_dynamic_constant_provider_regex_call_matching(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 50)
    _add_regex_call(provider, re.compile(r"[a-c]{3}"), "abc")
    assert not rpool.has_constant_for(str)


def test_dynamic_constant_provider_regex_call_limit(pool):
    provider = DynamicConstantProvider(pool, EmptyConstantProvider(), 0, 50)
    for _ in range(DynamicConstantProvider.MAX_REGEX_SEEDS_PER_PATTERN + 5):
        _add_regex_call(provider, re.compile(r"\d{4}"), "x")
    assert len(pool.get_all_constants_for(str)) <= (
        DynamicConstantProvider.MAX_REGEX_SEEDS_PER_PATTERN
    )
    assert provider._regex_seed_counts == {
        (r"\d{4}", re.UNICODE): DynamicConstantProvider.MAX_REGEX_SEEDS_PER_PATTERN
    }


def test_dynamic_constant_provider_regex_call_not_matching_generated(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 50)
    # The generator does not know about the VERBOSE flag.
    _add_regex_call(provider, re.compile(r"a b", re.VERBOSE), "x")
    assert not rpool.has_constant_for(str)


def test_dynamic_constant_provider_regex_call_generation_error(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 50)
    with mock.patch(
        "pynguin.analyses.constants.generate_from_regex", side_effect=RuntimeError("boom")
    ):
        _add_regex_call(provider, re.compile(r"a"), "x")
    assert not rpool.has_constant_for(str)


def test_dynamic_constant_provider_regex_call_not_regex(rpool):
    provider = DynamicConstantProvider(rpool, EmptyConstantProvider(), 0, 50)
    _add_regex_call(provider, object(), "x")
    assert not rpool.has_constant_for(str)
