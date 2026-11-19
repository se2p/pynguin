#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import logging

import pytest

import pynguin.configuration as config
from pynguin.utils.exceptions import ConfigurationException, ForbiddenModuleError
from pynguin.utils.forbidden_modules import (
    check_configured_module_allowed,
    check_module_allowed,
    matching_forbidden_pattern,
)


@pytest.mark.parametrize(
    "module_name, pattern",
    [
        ("semantic_release", "semantic_release"),
        ("semantic_release.cli", "semantic_release.*"),
        ("semantic_release.hvcs.github", "semantic_release.*"),
    ],
)
def test_forbidden_module_matches(module_name, pattern):
    assert matching_forbidden_pattern(module_name) == pattern
    with pytest.raises(ForbiddenModuleError) as info:
        check_module_allowed(module_name)
    assert info.value.module_name == module_name
    assert info.value.pattern == pattern
    assert module_name in str(info.value)


@pytest.mark.parametrize(
    "module_name",
    ["semantic_releases", "my_semantic_release", "tests.fixtures.semantic_release", "queue"],
)
def test_allowed_module(module_name):
    assert matching_forbidden_pattern(module_name) is None
    check_module_allowed(module_name)


def test_forbidden_module_error_is_configuration_exception():
    assert issubclass(ForbiddenModuleError, ConfigurationException)


def _configuration(module_name: str, *, check: bool) -> config.Configuration:
    return config.Configuration(
        project_path="",
        module_name=module_name,
        test_case_output=config.TestCaseOutputConfiguration(output_path=""),
        check_forbidden_modules=check,
    )


def test_check_forbidden_modules_enabled_by_default():
    assert config.Configuration(
        project_path="",
        module_name="foo",
        test_case_output=config.TestCaseOutputConfiguration(output_path=""),
    ).check_forbidden_modules


def test_configured_check_enabled_raises():
    with pytest.raises(ForbiddenModuleError):
        check_configured_module_allowed(_configuration("semantic_release.cli", check=True))


def test_configured_check_disabled_warns(caplog):
    with caplog.at_level(logging.WARNING):
        check_configured_module_allowed(_configuration("semantic_release.cli", check=False))
    assert "semantic_release.cli" in caplog.text
    assert "check is disabled" in caplog.text


@pytest.mark.parametrize("check", [True, False])
def test_configured_check_allowed_module_is_silent(caplog, check):
    with caplog.at_level(logging.WARNING):
        check_configured_module_allowed(_configuration("queue", check=check))
    assert not caplog.text
