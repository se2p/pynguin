#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses for the subject module, based on the module and its AST."""
import ast
import importlib
import inspect
import logging
import sys
from types import ModuleType
from typing import NamedTuple

LOGGER = logging.getLogger(__name__)


class _ParseResult(NamedTuple):
    """A data wrapper for an imported and parsed module."""

    module_name: str
    module: ModuleType
    syntax_tree: ast.AST | None


def parse_module(module_name: str) -> _ParseResult:
    """Parses a module and extracts its module-type and AST.

    If the source code is not available it is not possible to build an AST.  In this
    case the respective field of the :py:class:`_ParseResult` will contain the value
    ``None``.  This is the case, for example, for modules written in native code,
    for example, in C.

    Args:
        module_name: The fully-qualified name of the module

    Returns:
        A tuple of the imported module type and its optional AST
    """
    module = importlib.import_module(module_name)

    try:
        syntax_tree = ast.parse(
            inspect.getsource(module),
            filename=module_name.split(".")[-1] + ".py",
            type_comments=True,
            feature_version=sys.version_info[:2],
        )
    except OSError as error:
        LOGGER.warning(
            f"Could not retrieve source code for module {module_name} ({error})."
        )
        syntax_tree = None
    return _ParseResult(module_name=module_name, module=module, syntax_tree=syntax_tree)
