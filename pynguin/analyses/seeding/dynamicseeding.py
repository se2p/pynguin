#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Instruments the bytecode to perform dynamic constant seeding."""
from __future__ import annotations

import logging
import os
from typing import Dict, Set, Union, Type

from pynguin.utils import randomness

# Variables for this types are stored in the dynamic pool.
Types = Union[int, float, str]


# pylint:disable=unsubscriptable-object
class DynamicSeeding:
    """Provides the dynamic pool and methods to add values to and get values from the
     dynamic pool.

    The methods in this class are added to the module under test during an instruction
    phase before the main algorithm is executed. During this instruction phase,
    bytecode is added to the module under test which executes the methods adding
    values to the dynamic pool. The instrumentation is implemented in the module
    dynamicseedinginstrumentation.py.

    During the test generation process when a new value of one of the supported types
    is needed, this module provides methods to get values from the dynamic pool
    instead of randomly generating a new one.

    """

    _logger = logging.getLogger(__name__)

    _dynamic_pool: Dict[Type[Types], Set] = {int: set(), float: set(), str: set()}

    _string_functions_lookup = {
        "isalnum": lambda value: f"{value}!" if value.isalnum() else "isalnum",
        "islower": lambda value: value.upper() if value.islower() else value.lower(),
        "isupper": lambda value: value.lower() if value.isupper() else value.upper(),
        "isdecimal": lambda value: "non_decimal" if value.isdecimal() else "0123456789",
        "isalpha": lambda value: f"{value}1" if value.isalpha() else "isalpha",
        "isdigit": lambda value: f"{value}_" if value.isdigit() else "0",
        "isidentifier": lambda value: f"{value}!"
        if value.isidentifier()
        else "is_Identifier",
        "isnumeric": lambda value: f"{value}A" if value.isnumeric() else "012345",
        "isprintable": lambda value: f"{value}{os.linesep}"
        if value.isprintable()
        else "is_printable",
        "isspace": lambda value: f"{value}a" if value.isspace() else "   ",
        "istitle": lambda value: f"{value} AAA" if value.istitle() else "Is Title",
    }

    @property
    def has_ints(self) -> bool:
        """Whether or not the pool stores ints.

        Returns:
            Whether or not the pool stores ints
        """
        return self.has_constants(int)

    @property
    def has_floats(self) -> bool:
        """Whether or not the pool stores floats.

        Returns:
            Whether or not the pool stores floats
        """
        return self.has_constants(float)

    @property
    def has_strings(self) -> bool:
        """Whether or not the pool stores strings.

        Returns:
            Whether or not the pool stores strings
        """
        return self.has_constants(str)

    def has_constants(self, type_: Type[Types]) -> bool:
        """Whether or not the pool has constants of a given type.

        Args:
            type_: The type name

        Returns:
            Whether or not the pool has constants
        """
        assert type_ in self._dynamic_pool
        return len(self._dynamic_pool[type_]) > 0

    @property
    def random_int(self) -> int:
        """Provides a random integer.

        Returns:
            A random int from the pool
        """
        rand_value = randomness.choice(tuple(self._dynamic_pool[int]))
        return rand_value

    @property
    def random_float(self) -> float:
        """Provides a random float.

        Returns:
            A random float from the pool
        """
        rand_value = randomness.choice(tuple(self._dynamic_pool[float]))
        return rand_value

    @property
    def random_string(self) -> str:
        """Provides a random string.

        Returns:
            A random string from the pool
        """
        rand_value = randomness.choice(tuple(self._dynamic_pool[str]))
        return rand_value

    def add_value(self, value: Types):
        """Adds the given value to the corresponding set of the dynamic pool.

        Args:
            value: The value to add.
        """
        if isinstance(
            value, bool
        ):  # needed because True and False are accepted as ints otherwise
            return
        if type(value) in self._dynamic_pool:
            self._dynamic_pool[type(value)].add(value)

    def add_value_for_strings(self, value: str, name: str):
        """Add a value of a string.

        Args:
            value: The value
            name: The string
        """
        if not isinstance(value, str):
            return
        self._dynamic_pool[str].add(value)
        self._dynamic_pool[str].add(self._string_functions_lookup[name](value))


# Singleton instance of Dynamic Seeding.
INSTANCE = DynamicSeeding()
