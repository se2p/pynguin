#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the static return-value setup analyzer."""

from __future__ import annotations

from pynguin.large_language_model.mock_generation.mock_generator import RaiseException
from pynguin.large_language_model.mock_generation.static_setups import module_setups


def test_branch_constant_direct_attribute():
    src = "def f(resp):\n    if resp.status_code == 200:\n        return 1\n"
    mutable, lines = module_setups(src)
    assert ("status_code", [200, 201]) in mutable
    assert lines == []


def test_branch_constant_through_call():
    src = "def f(resp):\n    if resp.get().code == 404:\n        return 1\n"
    mutable, _ = module_setups(src)
    assert ("get.return_value.code", [404, 405]) in mutable


def test_constant_on_left_or_right():
    src = "def f(r):\n    if 500 == r.status:\n        return 1\n"
    mutable, _ = module_setups(src)
    assert ("status", [500, 501]) in mutable


def test_multiple_constants_same_attribute_are_unioned():
    src = (
        "def f(r):\n"
        "    if r.code == 200:\n        return 1\n"
        "    if r.code == 404:\n        return 2\n"
    )
    mutable, _ = module_setups(src)
    chains = dict(mutable)
    assert set(chains["code"]) >= {200, 404}


def test_iteration_over_call_result():
    src = "def f(items):\n    for it in items.all():\n        print(it)\n"
    _, lines = module_setups(src)
    assert "m.all.return_value = [MagicMock()]" in lines


def test_iteration_over_param_itself():
    src = "def f(seq):\n    for x in seq:\n        print(x)\n"
    _, lines = module_setups(src)
    assert "m.__iter__.return_value = iter([MagicMock()])" in lines


def test_non_param_and_non_constant_ignored():
    src = "def f(a, b):\n    x = 1\n    if x == 2:\n        return a + b\n"
    mutable, lines = module_setups(src)
    assert mutable == []
    assert lines == []


def test_string_constant_candidate():
    src = "def f(r):\n    if r.method == 'GET':\n        return 1\n"
    mutable, _ = module_setups(src)
    assert ("method", ["GET"]) in mutable


def test_syntax_error_is_safe():
    assert module_setups("def broken(") == ([], [])


def test_alias_local_from_param_call():
    # resp = session.get(...); if resp.status_code == 200 -> chain through the call.
    src = (
        "def f(session):\n"
        "    resp = session.get('/x')\n"
        "    if resp.status_code == 200:\n        return 1\n"
        "    if resp.status_code == 404:\n        return 2\n"
    )
    mutable, _ = module_setups(src)
    chains = dict(mutable)
    assert "get.return_value.status_code" in chains
    assert set(chains["get.return_value.status_code"]) >= {200, 404}


def test_truthiness_guard():
    src = "def f(cfg):\n    if cfg.enabled:\n        return 1\n    return 0\n"
    mutable, _ = module_setups(src)
    chains = dict(mutable)
    assert "enabled" in chains
    assert set(chains["enabled"]) == {True, None}


def test_not_truthiness_guard():
    src = "def f(cfg):\n    if not cfg.debug:\n        return 1\n"
    mutable, _ = module_setups(src)
    assert "debug" in dict(mutable)


def test_is_none_guard():
    src = "def f(r):\n    x = r.load()\n    if x is None:\n        return 1\n"
    mutable, _ = module_setups(src)
    chains = dict(mutable)
    assert "load.return_value" in chains
    assert None in chains["load.return_value"]


def test_truthiness_through_boolop():
    src = "def f(a):\n    if a.x and a.y:\n        return 1\n"
    mutable, _ = module_setups(src)
    chains = dict(mutable)
    assert "x" in chains
    assert "y" in chains


def test_alias_iteration_through_local():
    src = (
        "def f(session):\n"
        "    resp = session.fetch()\n"
        "    for row in resp.rows():\n        print(row)\n"
    )
    _, lines = module_setups(src)
    assert "m.fetch.return_value.rows.return_value = [MagicMock()]" in lines


def test_len_seeded_mutable():
    src = "def f(x):\n    if len(x) > 0:\n        return 1\n"
    mutable, _ = module_setups(src)
    chains = dict(mutable)
    assert "__len__.return_value" in chains
    assert set(chains["__len__.return_value"]) >= {0, 1}


def test_membership_seeded():
    src = "def f(r):\n    if 'k' in r.meta:\n        return 1\n"
    mutable, _ = module_setups(src)
    assert "meta.__contains__.return_value" in dict(mutable)


def test_subscript_setup_line():
    src = "def f(r):\n    return r.data['k']\n"
    _, lines = module_setups(src)
    assert "m.data.__getitem__.return_value = MagicMock()" in lines


def test_numeric_default_for_arithmetic():
    src = "def f(r):\n    return r.count() + 1\n"
    _, lines = module_setups(src)
    assert "m.count.return_value = 0" in lines


def test_exception_seeding_builtin():
    src = (
        "def f(store, key):\n"
        "    try:\n"
        "        v = store.load(key)\n"
        "    except KeyError:\n"
        "        v = None\n"
        "    return v\n"
    )
    mutable, _ = module_setups(src)
    chains = dict(mutable)
    assert "load.side_effect" in chains
    cands = chains["load.side_effect"]
    assert None in cands
    assert RaiseException(name="KeyError") in cands


def test_exception_seeding_ignores_non_builtin():
    src = (
        "def f(session):\n"
        "    try:\n"
        "        r = session.get('/')\n"
        "    except requests.ConnectionError:\n"
        "        r = None\n"
        "    return r\n"
    )
    mutable, _ = module_setups(src)
    assert "get.side_effect" not in dict(mutable)
