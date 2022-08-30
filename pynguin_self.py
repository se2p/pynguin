#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Generate a version of Pynguin which belongs to a separate package in order
to apply pynguin to itself."""
import os
import shutil
import typing
import libcst as cst
from pathlib import Path

SOURCE_PACKAGE_PREFIX = "pynguin"
TARGET_PACKAGE_PREFIX = "pynguin_self"


class ImportTransformer(cst.CSTTransformer):
    """A transformer that replaces imports from the source to the target package
    prefix"""

    def leave_ImportFrom(
        self, original_node: "cst.ImportFrom", updated_node: "cst.ImportFrom"
    ) -> "typing.Union[cst.BaseSmallStatement, cst.FlattenSentinel[cst.BaseSmallStatement], cst.RemovalSentinel]":
        module = updated_node.module
        while isinstance(module, cst.Attribute):
            module = module.value
        if isinstance(module, cst.Name) and module.value == SOURCE_PACKAGE_PREFIX:
            return updated_node.deep_replace(module, cst.Name(TARGET_PACKAGE_PREFIX))
        return updated_node

    def leave_Import(
        self, original_node: "cst.Import", updated_node: "cst.Import"
    ) -> "typing.Union[cst.BaseSmallStatement, cst.FlattenSentinel[cst.BaseSmallStatement], cst.RemovalSentinel]":
        to_replace = []
        for name in updated_node.names:
            node = name.name
            while isinstance(node, cst.Attribute):
                node = node.value
            if isinstance(node, cst.Name) and node.value == SOURCE_PACKAGE_PREFIX:
                to_replace.append(node)
        for replacement in to_replace:
            updated_node = updated_node.deep_replace(replacement, cst.Name(TARGET_PACKAGE_PREFIX))
        return updated_node


if __name__ == '__main__':
    # Required for 3.10 parser support
    os.environ["LIBCST_PARSER_TYPE"] = "native"

    # We need to move Pynguin's root to a different package, so we don't have
    # collisions of packages during testing, e.g., to avoid instrumenting ourselves.
    target_dir = Path(TARGET_PACKAGE_PREFIX)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(Path(SOURCE_PACKAGE_PREFIX), target_dir)
    transformer = ImportTransformer()
    for python_file in target_dir.rglob("*.py"):
        # Rewrite imports to use TARGET_PACKAGE_PREFIX
        content = python_file.read_text("UTF-8")
        parsed = cst.parse_module(content)
        changed_imports = parsed.visit(transformer)
        python_file.write_text(changed_imports.code, "UTF-8")


