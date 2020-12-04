#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Implements a simple static constant seeding strategy."""
from __future__ import annotations

import ast
import logging
import os
from pkgutil import iter_modules
from typing import Any, Dict, Optional, Set, Union, cast

from setuptools import find_packages

from pynguin.utils import randomness

Types = Union[float, int, str]


class InitialPopulationSeeding:
    """A simple static constant seeding strategy.

    Extracts all constants from a set of modules by using an AST visitor.
    """

    _logger = logging.getLogger(__name__)
    _instance: Optional[InitialPopulationSeeding] = None

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

    def collect_constants(
        self, project_path: Union[str, os.PathLike]
    ) -> Dict[str, Set[Types]]:
        """Collect all constants for a given project.

        Args:
            project_path: The path to the project's root

        Returns:
            A dict of type to set of constants
        """
        assert self._constants is not None
        for module in self._find_modules(project_path):
            with open(os.path.join(project_path, module)) as module_file:
                try:
                    tree = ast.parse(module_file.read())
                    #collector.visit(tree)
                except BaseException as exception:  # pylint: disable=broad-except
                    self._logger.debug("Cannot collect constants: %s", exception)
        self._constants = None #collector.constants
        return self._constants



