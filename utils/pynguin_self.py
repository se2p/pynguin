#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Generate a version of Pynguin which belongs to a separate package in order
to apply pynguin to itself."""
import dataclasses
import os
import shutil
import sys
import tempfile
import typing

from pathlib import Path

import libcst as cst
import simple_parsing


class ImportTransformer(cst.CSTTransformer):
    """A transformer that replaces imports from the source to the target package
    prefix"""

    def __init__(self, source_package_prefix: str, target_package_prefix: str):
        """Create new import transformer

        Args:
            source_package_prefix: the source package prefix
            target_package_prefix: the target package prefix
        """
        super().__init__()
        self._source_package_prefix = source_package_prefix
        self._target_package_prefix = target_package_prefix

    def leave_ImportFrom(
        self, original_node: "cst.ImportFrom", updated_node: "cst.ImportFrom"
    ) -> "typing.Union[cst.BaseSmallStatement, cst.FlattenSentinel[cst.BaseSmallStatement], cst.RemovalSentinel]":
        module = updated_node.module
        while isinstance(module, cst.Attribute):
            module = module.value
        if isinstance(module, cst.Name) and module.value == self._source_package_prefix:
            return updated_node.deep_replace(
                module, cst.Name(self._target_package_prefix)
            )
        return updated_node

    def leave_Import(
        self, original_node: "cst.Import", updated_node: "cst.Import"
    ) -> "typing.Union[cst.BaseSmallStatement, cst.FlattenSentinel[cst.BaseSmallStatement], cst.RemovalSentinel]":
        to_replace = []
        for name in updated_node.names:
            node = name.name
            while isinstance(node, cst.Attribute):
                node = node.value
            if isinstance(node, cst.Name) and node.value == self._source_package_prefix:
                to_replace.append(node)
        for replacement in to_replace:
            updated_node = updated_node.deep_replace(
                replacement, cst.Name(self._target_package_prefix)
            )
        return updated_node


@dataclasses.dataclass
class Config:
    target_dir: str | None = None
    """Location where the new copy of pynguin resides.
    Defaults to the temporary directory."""

    source_package_prefix: str = "pynguin"
    """Old package prefix, this will likely never change."""

    target_package_prefix: str = "pynguin_self"
    """The new package prefix."""


if __name__ == "__main__":
    arg_parser = simple_parsing.ArgumentParser(
        add_option_string_dash_variants=simple_parsing.DashVariant.UNDERSCORE_AND_DASH,
        description="A small utility to move Pynguin to a different package prefix.",
    )
    arg_parser.add_arguments(Config, dest="config")
    parsed = arg_parser.parse_args()
    config: Config = parsed.config

    # Required for 3.10 parser support
    os.environ["LIBCST_PARSER_TYPE"] = "native"

    # We need to move Pynguin's root to a different package, so we don't have
    # collisions of packages during testing, e.g., to avoid instrumenting ourselves.

    project_dir = Path(__file__).resolve().parents[1]
    source_dir = project_dir / Path(config.source_package_prefix)
    print(f"Source directory is '{source_dir}'")

    if config.target_dir is None:
        print("No target directory provided. Creating temporary one.")
        target_dir = tempfile.mkdtemp()
        # Place project in a subdirectory.
        target_dir /= Path("PynguinSelf")
    else:
        target_dir = Path(config.target_dir)
    print(f"Target directory is '{target_dir}'")

    if target_dir.exists():
        confirmed = input("Target directory exists. Clean up? [y/n]: ")
        if confirmed.lower() != "y":
            print("Aborting")
            sys.exit(1)
        shutil.rmtree(target_dir)

    target_package_dir = target_dir / Path(config.target_package_prefix)

    print("Copying files from source to target")
    shutil.copytree(source_dir, target_package_dir)
    transformer = ImportTransformer(
        config.source_package_prefix, config.target_package_prefix
    )
    print("Adjusting imports in copied files")
    for python_file in target_package_dir.rglob("*.py"):
        # Rewrite imports to use new prefix.
        content = python_file.read_text("UTF-8")
        parsed = cst.parse_module(content)
        changed_imports = parsed.visit(transformer)
        python_file.write_text(changed_imports.code, "UTF-8")
    print("Successfully adjusted all files.")
    print(
        "You can now run pynguin on itself running a variation of the following command:"
    )
    print(
        f"PYTHONPATH=$PYTHONPATH:{target_dir}"
        f" poetry run python {target_package_dir}/__main__.py"
        f" --project-path {project_dir}"
        f" --module-name pynguin.utils.orderedset"
        f" --output-path {project_dir}/tests -v"
    )
