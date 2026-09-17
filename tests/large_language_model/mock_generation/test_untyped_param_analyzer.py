#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the untyped-parameter analyzer."""

from __future__ import annotations

from pynguin.large_language_model.mock_generation.untyped_param_analyzer import (
    match_candidate_classes,
    match_param_boundaries,
    untyped_param_attr_sets,
    untyped_param_bindings,
)

# untyped_param_attr_sets


def test_direct_attribute_access_on_untyped_param():
    src = "def f(client, path):\n    return client.request('GET', path)\n"
    assert untyped_param_attr_sets(src) == [{"request"}]


def test_typed_param_is_ignored():
    src = "import requests\ndef f(client: requests.Session):\n    return client.get('/x')\n"
    assert untyped_param_attr_sets(src) == []


def test_param_without_object_use_is_ignored():
    src = "def f(a, b):\n    return a + b\n"
    assert untyped_param_attr_sets(src) == []


def test_multiple_attributes_collected():
    src = "def f(c):\n    c.request('GET', '/')\n    return c.close()\n"
    assert untyped_param_attr_sets(src) == [{"request", "close"}]


def test_constructor_injected_param_tracked_across_methods():
    src = (
        "class Service:\n"
        "    def __init__(self, session):\n"
        "        self._s = session\n"
        "    def run(self):\n"
        "        return self._s.request('GET', '/')\n"
    )
    assert untyped_param_attr_sets(src) == [{"request"}]


def test_constructor_param_not_stored_is_not_tracked_cross_method():
    src = (
        "class Service:\n"
        "    def __init__(self, session):\n"
        "        self._n = 1\n"
        "    def run(self):\n"
        "        return self._s.request('GET', '/')\n"
    )
    assert untyped_param_attr_sets(src) == []


def test_self_is_never_a_candidate():
    src = "class C:\n    def m(self):\n        return self.value\n"
    assert untyped_param_attr_sets(src) == []


# match_candidate_classes


class _WithRequest:
    def request(self):
        pass


class _AlsoWithRequest:
    def request(self):
        pass


class _Plain:
    pass


def test_match_keeps_classes_having_all_attributes():
    matched = match_candidate_classes([{"request"}], [_WithRequest, _Plain, dict])
    names = set(matched)
    assert any(n.endswith("._WithRequest") for n in names)
    assert not any(n.endswith("._Plain") for n in names)


def test_match_requires_every_attribute_in_set():
    matched = match_candidate_classes([{"request", "missing"}], [_WithRequest])
    assert matched == {}


def test_match_empty_attr_sets_matches_nothing():
    assert match_candidate_classes([], [_WithRequest]) == {}


# untyped_param_bindings — keyed by (callable qualname, param)


def test_bindings_key_module_level_function():
    src = "def f(s):\n    return s.request()\n"
    assert untyped_param_bindings(src) == {("f", "s"): {"request"}}


def test_bindings_key_method_qualname():
    src = "class C:\n    def m(self, s):\n        return s.get()\n"
    assert untyped_param_bindings(src) == {("C.m", "s"): {"get"}}


def test_bindings_constructor_param_attributed_to_init():
    src = (
        "class C:\n"
        "    def __init__(self, dep):\n"
        "        self.dep = dep\n"
        "    def run(self):\n"
        "        return self.dep.request()\n"
    )
    assert untyped_param_bindings(src) == {("C.__init__", "dep"): {"request"}}


def test_bindings_typed_param_ignored():
    src = "def f(s: int):\n    return s.request()\n"
    assert untyped_param_bindings(src) == {}


def test_attr_sets_still_derived_from_bindings():
    src = "def f(s):\n    return s.request()\n"
    assert untyped_param_attr_sets(src) == [{"request"}]


# match_param_boundaries — (qualname, param) -> class FQN


def test_match_param_boundaries_binds_unique_match():
    bindings = {("f", "s"): {"request"}}
    matched = match_param_boundaries(bindings, [_WithRequest, _Plain])
    assert list(matched) == [("f", "s")]
    assert matched["f", "s"].endswith("._WithRequest")


def test_match_param_boundaries_no_match():
    bindings = {("f", "s"): {"request", "missing"}}
    assert match_param_boundaries(bindings, [_WithRequest]) == {}


def test_match_param_boundaries_ambiguous_match_skipped():
    # Two candidate classes both satisfy the attribute usage -> not unique -> skip.
    bindings = {("f", "s"): {"request"}}
    assert match_param_boundaries(bindings, [_WithRequest, _AlsoWithRequest]) == {}


# Primitive-signature guard: a parameter used only via built-in scalar methods is
# a primitive (str/bytes/number), not a boundary, so it must not be bound.


def test_string_signature_param_not_bound():
    # A URL-string parameter used via str methods (the redis.connection over-bind)
    # must not produce a binding.
    src = "def f(url):\n    return url.replace('a', 'b').split('/')[0].startswith('x')\n"
    assert untyped_param_bindings(src) == {}
    assert untyped_param_attr_sets(src) == []


def test_bytes_signature_param_not_bound():
    src = "def f(buf):\n    return buf.decode().strip()\n"
    assert untyped_param_bindings(src) == {}


def test_domain_method_survives_alongside_primitive_attrs():
    # A parameter that also calls a non-primitive domain method (`request`) is a
    # boundary object and must still be bound, despite the str-shaped `.split`.
    src = "def f(c):\n    c.request('GET', '/')\n    return c.split('/')\n"
    assert untyped_param_bindings(src) == {("f", "c"): {"request", "split"}}


def test_dict_style_get_still_bound():
    # `get` overlaps with dict but is common domain vocabulary (e.g. HTTP client);
    # it is not treated as primitive.
    src = "def f(s):\n    return s.get('/x')\n"
    assert untyped_param_bindings(src) == {("f", "s"): {"get"}}
