#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements seeding of the initial population with previously existing testcases."""
from __future__ import annotations

import ast
import logging
import os
from pkgutil import iter_modules
from typing import Any, Dict, Optional, Set, Union, cast, List

from setuptools import find_packages

from pynguin.testcase.testcase import TestCase
from pynguin.utils import randomness

Types = Union[float, int, str]


class InitialPopulationSeeding:
    """Class for seeding the initial population with previously existing testcases.
    """

    _logger = logging.getLogger(__name__)
    _instance: Optional[InitialPopulationSeeding] = None
    _testcases: List[TestCase] = []

    def __new__(cls) -> InitialPopulationSeeding:
        if cls._instance is None:
            cls._instance = super(InitialPopulationSeeding, cls).__new__(cls)
        return cls._instance

    @staticmethod
    def _find_modules(project_path: Union[str, os.PathLike]) -> Set[str]:
        modules: Set[str] = set()
        for package in find_packages(
            project_path,
            exclude=[
                "*.tests",
                "*.tests.*",
                "tests.*",
                "tests",
                "test",
                "test.*",
                "*.test.*",
                "*.test",
            ],
        ):
            pkg_path = "{}/{}".format(project_path, package.replace(".", "/"))
            for info in iter_modules([pkg_path]):
                if not info.ispkg:
                    name = info.name.replace(".", "/")
                    package_path = package.replace(".", "/")
                    modules.add(f"{package_path}/{name}.py")
        return modules

    def get_ast_tree(
        self, project_path: Union[str, os.PathLike]
    ) -> ast.AST:
        """Returns the ast tree from a module

        Args:
            project_path: The path to the project's root

        Returns:
            The ast tree of the given module.
        """
        for module in self._find_modules(project_path):
            with open(os.path.join(project_path, module)) as module_file:
                try:
                    tree = ast.parse(module_file.read())
                except BaseException as exception:  # pylint: disable=broad-except
                    self._logger.debug("Cannot read module: %s", exception)
        return tree

    def get_internal_representation(self, tree: ast.AST):
        """Returns the initial representation of the given AST."""

    def collect_testcases(self, project_path: Union[str, os.PathLike]):
        pass
