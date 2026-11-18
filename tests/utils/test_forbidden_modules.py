#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.utils.exceptions import ConfigurationException, ForbiddenModuleError
from pynguin.utils.forbidden_modules import check_module_allowed, matching_forbidden_pattern


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
