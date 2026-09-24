#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for Step B return-value hint generation."""

from __future__ import annotations

from unittest.mock import patch

import requests

from pynguin.mock_generation import mock_hint_generator as hg

_GEN = "pynguin.mock_generation.llm_classifier_client.generate_mock_config"

_TARGET = "requests.sessions.Session"


def _write(tmp_path, source):
    path = tmp_path / "sut.py"
    path.write_text(source, encoding="utf-8")
    return path


def test_typed_param_identified_via_canonical_fqn(tmp_path):
    src = "import requests\ndef f(s: requests.Session):\n    return s.request('GET', '/')\n"
    module = _write(tmp_path, src)
    setup = "m.request.return_value.status_code = 200"
    response = {
        "mocks": [
            {
                "dependency": "s",
                "mock_target": _TARGET,
                "import_path": "requests",
                "methods": [{"method_name": "request", "return_value_setup": setup}],
            }
        ]
    }
    with patch(_GEN, return_value=response) as gen:
        templates = hg.generate_templates(module, {_TARGET}, [requests.sessions.Session])

    gen.assert_called_once()
    assert _TARGET in templates
    # A primitive-valued setup becomes a mutable setup (search varies the value).
    setups = templates[_TARGET].mutable_setups
    assert [s.target for s in setups] == ["request.return_value.status_code"]
    assert 200 in setups[0].candidates


def test_untyped_param_identified_via_usage(tmp_path):
    src = "def f(client, path):\n    return client.request('GET', path)\n"
    module = _write(tmp_path, src)
    with patch(_GEN, return_value={"mocks": []}) as gen:
        hg.generate_templates(module, {_TARGET}, [requests.sessions.Session])
    # `client` (untyped) is used with .request -> matched to Session -> hint requested.
    gen.assert_called_once()


def test_untyped_param_from_injector_bindings(tmp_path):
    # `conn` has no annotation and no local usage the weak matcher would catch
    # (and candidate_classes is empty), but the injector bound it. The hint
    # generator must still request a hint for exactly that param.
    src = "def f(conn, n):\n    return do(conn)\n"
    module = _write(tmp_path, src)
    bindings = {("sut.f", "conn"): _TARGET}
    with patch(_GEN, return_value={"mocks": []}) as gen:
        hg.generate_templates(module, {_TARGET}, [], module_name="sut", untyped_bindings=bindings)
    gen.assert_called_once()
    deps = gen.call_args.args[2]
    assert [d["name"] for d in deps] == ["conn"]
    assert deps[0]["mock_target"] == _TARGET


def test_method_param_hinted_via_injector_bindings(tmp_path):
    # The boundary is a *method* parameter (common in OOP code). generate_templates
    # must descend into the class and use the injector's `C.m` binding + cache key.
    src = "class Adapter:\n    def send(self, request):\n        return request.url\n"
    module = _write(tmp_path, src)
    bindings = {("sut.Adapter.send", "request"): _TARGET}
    with patch(_GEN, return_value={"mocks": []}) as gen:
        hg.generate_templates(module, {_TARGET}, [], module_name="sut", untyped_bindings=bindings)
    gen.assert_called_once()
    assert gen.call_args.args[0] == "sut.Adapter.send"  # module.Class.method cache key
    deps = gen.call_args.args[2]
    assert [d["name"] for d in deps] == ["request"]


def test_method_self_not_mocked_in_injector_mode(tmp_path):
    # A method with no injector binding must NOT fall back to mocking `self`/`x`.
    src = "class C:\n    def m(self, x):\n        return self.do(x)\n"
    module = _write(tmp_path, src)
    with patch(_GEN) as gen:
        hg.generate_templates(module, {_TARGET}, [], module_name="sut", untyped_bindings={})
    gen.assert_not_called()


def test_no_mocked_params_makes_no_proxy_call(tmp_path):
    src = "def f(a, b):\n    return a + b\n"
    module = _write(tmp_path, src)
    with patch(_GEN) as gen:
        templates = hg.generate_templates(module, {_TARGET}, [requests.sessions.Session])
    gen.assert_not_called()
    assert templates == {}


def test_merge_accumulates_setup_lines_by_target():
    templates: dict = {}
    # A non-primitive RHS (attribute) stays a raw setup line, not a mutable setup.
    setup = "m.request.return_value.headers = m.headers"
    method = {"method_name": "request", "return_value_setup": setup}
    response = {
        "mocks": [
            # Proxy echoes a non-canonical mock_target; matched via dependency name.
            {"dependency": "session", "mock_target": "requests.Session", "methods": [method]},
        ]
    }
    hg._merge(templates, response, {"session": _TARGET})
    assert list(templates) == [_TARGET]
    assert templates[_TARGET].setup_lines == [setup]


def test_merge_primitive_setup_becomes_mutable():
    templates: dict = {}
    method = {"method_name": "get", "return_value_setup": "m.get.return_value.status_code = 200"}
    response = {"mocks": [{"dependency": "s", "mock_target": _TARGET, "methods": [method]}]}
    hg._merge(templates, response, {"s": _TARGET}, {int: [200, 500]})
    setups = templates[_TARGET].mutable_setups
    assert setups[0].target == "get.return_value.status_code"
    # pool = original + branch constants + one out-of-range value.
    assert 200 in setups[0].candidates
    assert 500 in setups[0].candidates


def test_generate_proxy_error_is_swallowed(tmp_path):
    src = "import requests\ndef f(s: requests.Session):\n    return s.request('GET', '/')\n"
    module = _write(tmp_path, src)
    with patch(_GEN, side_effect=RuntimeError("down")):
        templates = hg.generate_templates(module, {_TARGET}, [requests.sessions.Session])
    assert templates == {}
