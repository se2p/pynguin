#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Modules Pynguin refuses to generate tests for.

Some subjects cause harmful side effects when Pynguin executes them, beyond what the
usual sandboxing prevents. For example, python-semantic-release runs real git
commands in the working directory: generated tests created tags in a checkout and
pushed them to its remote. Pynguin stops before importing such a module.
"""

from __future__ import annotations

import fnmatch
import logging
from typing import TYPE_CHECKING

from pynguin.utils.exceptions import ForbiddenModuleError

if TYPE_CHECKING:
    from pynguin.configuration import Configuration

_LOGGER = logging.getLogger(__name__)

# Glob patterns (``fnmatch`` syntax) of module names Pynguin must not run on.
FORBIDDEN_MODULE_PATTERNS: tuple[str, ...] = (
    "semantic_release",
    "semantic_release.*",
)


def matching_forbidden_pattern(module_name: str) -> str | None:
    """Return the first forbidden pattern that matches the module name.

    Args:
        module_name: The fully qualified name of the module under test.

    Returns:
        The matching pattern, or None if the module is allowed.
    """
    for pattern in FORBIDDEN_MODULE_PATTERNS:
        if fnmatch.fnmatchcase(module_name, pattern):
            return pattern
    return None


def check_module_allowed(module_name: str) -> None:
    """Raise if the module under test is forbidden.

    Args:
        module_name: The fully qualified name of the module under test.

    Raises:
        ForbiddenModuleError: If the module matches a forbidden pattern.
    """
    if (pattern := matching_forbidden_pattern(module_name)) is not None:
        raise ForbiddenModuleError(module_name, pattern)


def check_configured_module_allowed(configuration: Configuration) -> None:
    """Raise if the configured module under test is forbidden and the check is on.

    With ``check_forbidden_modules`` disabled, a forbidden module only causes a
    warning.

    Args:
        configuration: The Pynguin configuration to check.

    Raises:
        ForbiddenModuleError: If the module matches a forbidden pattern and the check
            is enabled.
    """
    if configuration.check_forbidden_modules:
        check_module_allowed(configuration.module_name)
    elif (pattern := matching_forbidden_pattern(configuration.module_name)) is not None:
        _LOGGER.warning(
            "Module '%s' matches forbidden pattern '%s', but the forbidden-module "
            "check is disabled. Run it only in an isolated environment.",
            configuration.module_name,
            pattern,
        )
