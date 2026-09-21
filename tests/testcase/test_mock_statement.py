#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the libcst-backed mock statement builders."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.testcase.mock_statement as ms
from pynguin.large_language_model.mock_generation.mock_generator import (
    MockMethodConfig,
    MockParameter,
    MockTemplate,
    MutableSetup,
    RaiseException,
)
from pynguin.testcase.mock_statement import (
    build_mock_statement,
    create_mock_statement,
    current_setup_value,
    default_parameter_values,
    render_mock_node,
)
from pynguin.testcase.testfactory import TestFactory

# Helpers


def _make_template(
    *,
    dependency: str = "session",
    mock_target: str = "requests.Session",
    method_configs: list[MockMethodConfig] | None = None,
    parameters: list[MockParameter] | None = None,
    setup_lines: list[str] | None = None,
    attribute_values: dict | None = None,
    mutable_setups: list[MutableSetup] | None = None,
) -> MockTemplate:
    return MockTemplate(
        dependency=dependency,
        import_path=dependency.split(".", maxsplit=1)[0],
        mock_target=mock_target,
        method_configs=method_configs or [],
        setup_code="",
        parameters=parameters or [],
        attribute_values=attribute_values or {},
        setup_lines=setup_lines or [],
        mutable_setups=mutable_setups or [],
    )


def _make_method_config(
    method_name: str = "get",
    params: list[MockParameter] | None = None,
) -> MockMethodConfig:
    return MockMethodConfig(
        method_name=method_name,
        return_value_template="",
        parameters=params or [],
    )


def _make_param(
    name: str = "status_code",
    param_type: str = "int",
    default=200,
) -> MockParameter:
    return MockParameter(
        name=name,
        param_type=param_type,
        default_value=default,
        description="HTTP status code",
    )


def _code(statement) -> str:
    return cst.Module(body=[statement.node]).code


def _node_code(node) -> str:
    return cst.Module(body=[node]).code


def _stmt_code(test_case) -> str:
    return cst.Module(body=[test_case.get_statement(0).node]).code


# Construction


def test_build_binds_variable_and_mock_info():
    s = build_mock_statement("var_0", _make_template())
    assert s.bound_variable == "var_0"
    assert s.mock_info is not None
    assert s.mock_info.template is not None


def test_build_primary_node_is_magicmock():
    s = build_mock_statement("var_0", _make_template())
    assert "var_0 = MagicMock()" in _code(s)


def test_default_parameter_values():
    param = _make_param("status_code", "int", 200)
    template = _make_template(parameters=[param])
    s = build_mock_statement("var_0", template)
    assert s.mock_info.parameter_values == {"status_code": 200}


def test_explicit_parameter_values():
    param = _make_param("status_code", "int", 200)
    mc = _make_method_config("get", params=[param])
    template = _make_template(method_configs=[mc], parameters=[param])
    s = build_mock_statement("var_0", template, parameter_values={"status_code": 404})
    assert s.mock_info.parameter_values["status_code"] == 404
    assert "var_0.get.return_value = 404" in _code(s)


def test_parameter_values_are_copied():
    param = _make_param()
    template = _make_template(parameters=[param])
    original = {"status_code": 200}
    s = build_mock_statement("var_0", template, parameter_values=original)
    original["status_code"] = 999
    assert s.mock_info.parameter_values["status_code"] == 200


def test_setup_choices_are_copied():
    template = _make_template(
        mutable_setups=[MutableSetup(target="get.return_value.status_code", candidates=[200, 500])]
    )
    original = [1]
    s = build_mock_statement("var_0", template, setup_choices=original)
    original[0] = 0
    assert s.mock_info.setup_choices == [1]


def test_default_parameter_values_helper():
    template = _make_template(parameters=[_make_param("a", "int", 1), _make_param("b", "str", "x")])
    assert default_parameter_values(template) == {"a": 1, "b": "x"}


# Node rendering


def test_method_config_renders_return_value():
    mc = _make_method_config("get", params=[_make_param("status_code", "int", 200)])
    template = _make_template(method_configs=[mc], parameters=[_make_param()])
    code = _node_code(render_mock_node("var_0", template, [], {"status_code": 200}))
    assert "var_0.get.return_value = 200" in code


def test_method_config_without_params_uses_magicmock():
    mc = _make_method_config("post", params=[])
    template = _make_template(method_configs=[mc])
    code = _node_code(render_mock_node("var_0", template, [], {}))
    assert "var_0.post.return_value = MagicMock()" in code


def test_attribute_values_rendered():
    template = _make_template(attribute_values={"timeout": 30})
    code = _node_code(render_mock_node("var_0", template, [], {}))
    assert "var_0.timeout = 30" in code


def test_setup_lines_rendered_and_renamed():
    template = _make_template(setup_lines=["mock_s.request.return_value.status_code = 200"])
    code = _node_code(render_mock_node("var_0", template, [], {}))
    assert "var_0.request.return_value.status_code = 200" in code


def test_non_assignment_setup_lines_ignored():
    template = _make_template(setup_lines=["import os", "bad ((", "x = 1"])
    # "x = 1" has a bare Name target (not an attribute chain), so it is rejected too.
    code = _node_code(render_mock_node("var_0", template, [], {}))
    assert code.strip() == "var_0 = MagicMock()"


def test_mutable_setup_renders_current_value():
    template = _make_template(
        mutable_setups=[
            MutableSetup(target="get.return_value.status_code", candidates=[200, 500, 199])
        ]
    )
    code = _node_code(render_mock_node("var_0", template, [1], {}))
    assert "var_0.get.return_value.status_code = 500" in code


def test_mutable_setup_choice_wraps_around():
    template = _make_template(
        mutable_setups=[MutableSetup(target="x.return_value", candidates=[1, 2])]
    )
    # choice 3 % 2 == 1 -> second candidate
    code = _node_code(render_mock_node("var_0", template, [3], {}))
    assert "var_0.x.return_value = 2" in code


def test_raise_exception_candidate_renders_bare_name():
    template = _make_template(
        mutable_setups=[
            MutableSetup(target="get.side_effect", candidates=[RaiseException("KeyError")])
        ]
    )
    code = _node_code(render_mock_node("var_0", template, [0], {}))
    assert "var_0.get.side_effect = KeyError" in code


def test_string_value_rendered_as_literal():
    template = _make_template(attribute_values={"name": "hello"})
    code = _node_code(render_mock_node("var_0", template, [], {}))
    assert "var_0.name = 'hello'" in code


def test_current_setup_value_helper():
    template = _make_template(mutable_setups=[MutableSetup(target="a", candidates=[10, 20, 30])])
    assert current_setup_value(template, [2], 0) == 30


# _render_setup_line


def test_render_setup_line_renames_root_placeholder():
    node = ms._render_setup_line("mock_client.get.return_value.json.return_value = {}", "var_7")
    assert _node_code(cst.SimpleStatementLine(body=[node])).strip() == (
        "var_7.get.return_value.json.return_value = {}"
    )


def test_render_setup_line_rejects_bare_name_target():
    assert ms._render_setup_line("x = foo()", "var_0") is None


def test_render_setup_line_rejects_non_assignment():
    assert ms._render_setup_line("import os", "var_0") is None


def test_render_setup_line_rejects_malformed():
    assert ms._render_setup_line("bad ((", "var_0") is None


# create_mock_statement (inserts into a test case)


def test_create_mock_statement_inserts(default_test_case):
    var = create_mock_statement(default_test_case, _make_template(), 0)
    assert default_test_case.size() == 1
    stmt = default_test_case.get_statement(0)
    assert stmt.bound_variable == var
    assert stmt.mock_info is not None
    assert f"{var} = MagicMock()" in default_test_case.to_code()


# Clone / crossover survival


def test_clone_preserves_mock_info(default_test_case):
    template = _make_template(
        mutable_setups=[MutableSetup(target="get.return_value.status_code", candidates=[200, 404])]
    )
    var = default_test_case.next_var_name()
    default_test_case.add_statement(build_mock_statement(var, template, setup_choices=[1]))

    cloned = default_test_case.clone()
    stmt = cloned.get_statement(0)
    assert stmt.mock_info is not None
    assert stmt.mock_info.setup_choices == [1]
    assert cloned.to_code() == default_test_case.to_code()


# Mutation (via TestFactory)


def _mutable_template() -> MockTemplate:
    return _make_template(
        mutable_setups=[
            MutableSetup(target="get.return_value.status_code", candidates=[200, 500, 199])
        ]
    )


def _factory() -> TestFactory:
    return TestFactory(MagicMock())


def test_mutate_no_mutable_setups_and_no_params_returns_false(default_test_case):
    var = default_test_case.next_var_name()
    default_test_case.add_statement(build_mock_statement(var, _make_template()))
    assert _factory()._mutate_mock(default_test_case, 0) is False


def test_mutate_changes_setup_choice(default_test_case):
    var = default_test_case.next_var_name()
    default_test_case.add_statement(
        build_mock_statement(var, _mutable_template(), setup_choices=[0])
    )
    with (
        patch.object(config.configuration.search_algorithm, "change_parameter_probability", 1.0),
        patch("pynguin.testcase.testfactory.randomness.next_float", return_value=0.0),
        patch("pynguin.testcase.testfactory.randomness.next_int", return_value=1),
    ):
        changed = _factory()._mutate_mock(default_test_case, 0)
    assert changed is True
    stmt = default_test_case.get_statement(0)
    assert stmt.mock_info.setup_choices == [1]
    assert "var_0.get.return_value.status_code = 500" in _stmt_code(default_test_case)


def test_mutate_probability_zero_returns_false(default_test_case):
    var = default_test_case.next_var_name()
    default_test_case.add_statement(
        build_mock_statement(var, _mutable_template(), setup_choices=[0])
    )
    with patch("pynguin.testcase.testfactory.randomness.next_float", return_value=1.0):
        changed = _factory()._mutate_mock(default_test_case, 0)
    assert changed is False


def test_mutate_int_param(default_test_case):
    param = _make_param("status_code", "int", 200)
    mc = _make_method_config("get", params=[param])
    template = _make_template(method_configs=[mc], parameters=[param])
    var = default_test_case.next_var_name()
    default_test_case.add_statement(build_mock_statement(var, template))
    with (
        patch.object(config.configuration.search_algorithm, "change_parameter_probability", 1.0),
        patch("pynguin.testcase.testfactory.randomness.next_float", return_value=0.0),
        patch("pynguin.testcase.testfactory.randomness.next_int", return_value=5),
    ):
        changed = _factory()._mutate_mock(default_test_case, 0)
    assert changed is True
    assert default_test_case.get_statement(0).mock_info.parameter_values["status_code"] == 205


def test_mutate_bool_param(default_test_case):
    param = _make_param("flag", "bool", default=False)
    mc = _make_method_config("ok", params=[param])
    template = _make_template(method_configs=[mc], parameters=[param])
    var = default_test_case.next_var_name()
    default_test_case.add_statement(build_mock_statement(var, template))
    with (
        patch.object(config.configuration.search_algorithm, "change_parameter_probability", 1.0),
        patch("pynguin.testcase.testfactory.randomness.next_float", return_value=0.0),
        patch("pynguin.testcase.testfactory.randomness.next_bool", return_value=True),
    ):
        changed = _factory()._mutate_mock(default_test_case, 0)
    assert changed is True
    assert default_test_case.get_statement(0).mock_info.parameter_values["flag"] is True


def test_mutate_str_param(default_test_case):
    param = _make_param("msg", "str", default="hello")
    mc = _make_method_config("m", params=[param])
    template = _make_template(method_configs=[mc], parameters=[param])
    var = default_test_case.next_var_name()
    default_test_case.add_statement(build_mock_statement(var, template))
    with (
        patch.object(config.configuration.search_algorithm, "change_parameter_probability", 1.0),
        patch("pynguin.testcase.testfactory.randomness.next_float", return_value=0.0),
        patch("pynguin.testcase.testfactory.randomness.next_string", return_value="world"),
    ):
        changed = _factory()._mutate_mock(default_test_case, 0)
    assert changed is True
    assert default_test_case.get_statement(0).mock_info.parameter_values["msg"] == "world"


def test_mutate_value_dispatches_to_mock(default_test_case):
    var = default_test_case.next_var_name()
    default_test_case.add_statement(
        build_mock_statement(var, _mutable_template(), setup_choices=[0])
    )
    with (
        patch.object(config.configuration.search_algorithm, "change_parameter_probability", 1.0),
        patch("pynguin.testcase.testfactory.randomness.next_float", return_value=0.0),
        patch("pynguin.testcase.testfactory.randomness.next_int", return_value=2),
    ):
        changed = _factory().mutate_value(default_test_case, 0)
    assert changed is True
    assert default_test_case.get_statement(0).mock_info.setup_choices == [2]


@pytest.mark.parametrize("value", [200, "text", b"bytes", 1.5, True, None])
def test_various_constant_values_round_trip(value):
    template = _make_template(attribute_values={"v": value})
    code = _node_code(render_mock_node("var_0", template, [], {}))
    assert f"var_0.v = {value!r}" in code
