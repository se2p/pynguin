#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a loader for loading and reloading custom modules."""
import sys
from importlib import reload
from types import ModuleType
from typing import Dict


class ModuleLoader:
    """Class for handling loading modules."""

    _mutated_module_aliases: Dict[str, ModuleType] = {}

    @staticmethod
    def load_module(module_name: str) -> ModuleType:
        """
        Loads a module either from sys.modules or if a mutated version for the given
        module name exists than the mutated version of the module will be returned.

        Args:
            module_name: string for the module alias, which should be loaded

        Returns:
            the module which should be loaded.
        """
        mutated_module = ModuleLoader._mutated_module_aliases.get(module_name, None)
        if mutated_module:
            return mutated_module
        return sys.modules[module_name]

    @staticmethod
    def add_mutated_version(module_name: str, mutated_module: ModuleType) -> None:
        """
        Adds a mutated version of a module to the collection of mutated alias of
        normal modules.

        Args:
            module_name: for the module name of the module, which should be mutated.
            mutated_module: the custom module, which should be used.
        """
        ModuleLoader._mutated_module_aliases[module_name] = mutated_module

    @staticmethod
    def clear_mutated_modules() -> None:
        """
        Clears the dict of mutated modules.
        """
        ModuleLoader._mutated_module_aliases = {}

    @staticmethod
    def reload_module(module_name: str) -> None:
        """
        Reloads the given module.

        Args:
            module_name: the module to reload.
        """
        reload(sys.modules[module_name])
