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
from typing import Any, NamedTuple

LOGGER = logging.getLogger(__name__)


class _ParseResult(NamedTuple):
    """A data wrapper for an imported and parsed module."""

    module_name: str
    module: ModuleType
    syntax_tree: ast.AST | None
    contains_type_information: bool


class _ArgumentAnnotationRemovalVisitor(ast.NodeTransformer):
    """Removes argument annotations from an AST."""

    # pylint: disable=missing-function-docstring, no-self-use
    def visit_arg(self, node: ast.arg) -> Any:
        node.annotation = None
        return node


def parse_module(module_name: str, extract_types: bool = True) -> _ParseResult:
    """Parses a module and extracts its module-type and AST.

    If the source code is not available it is not possible to build an AST.  In this
    case the respective field of the :py:class:`_ParseResult` will contain the value
    ``None``.  This is the case, for example, for modules written in native code,
    for example, in C.

    Args:
        module_name: The fully-qualified name of the module
        extract_types: Whether to extract type information into the AST

    Returns:
        A tuple of the imported module type and its optional AST
    """
    module = importlib.import_module(module_name)

    try:
        syntax_tree = ast.parse(
            inspect.getsource(module),
            filename=module_name.split(".")[-1] + ".py",
            type_comments=extract_types,
            feature_version=sys.version_info[1],
        )
        if not extract_types:
            # The parameter type_comments of the AST library's parse function does not
            # prevent that the annotation is present in the AST.  Thus, we explicitly
            # remove it if we do not want the types to be extracted.
            # This is a hack, maybe I do not understand how to use ast.parse properly...
            annotation_remover = _ArgumentAnnotationRemovalVisitor()
            annotation_remover.visit(syntax_tree)
    except OSError as error:
        LOGGER.warning(
            f"Could not retrieve source code for module {module_name} ({error}). "
            f"Cannot derive syntax tree to allow Pynguin using more precise analysis."
        )
        syntax_tree = None
    return _ParseResult(
        module_name=module_name,
        module=module,
        syntax_tree=syntax_tree,
        contains_type_information=extract_types,
    )
