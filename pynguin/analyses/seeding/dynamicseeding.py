#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Instruments the bytecode to perform dynamic constant seeding."""
from __future__ import annotations

import logging
from typing import Dict, Optional, Set, Union, Type

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
    _instance: Optional[DynamicSeeding] = None

    def __new__(cls) -> DynamicSeeding:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._dynamic_pool = {int: set(), float: set(), str: set()}
        return cls._instance

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
        assert self._dynamic_pool is not None
        assert type_ in self._dynamic_pool
        return len(self._dynamic_pool.get(type_)) > 0

    @property
    def random_int(self) -> int:
        """Provides a random integer.

        Returns:
            A random int from the pool
        """
        assert self._dynamic_pool is not None
        rand_value = randomness.choice(tuple(self._dynamic_pool[int]))
        return rand_value

    @property
    def random_float(self) -> float:
        """Provides a random float.

        Returns:
            A random float from the pool
        """
        assert self._dynamic_pool is not None
        rand_value = randomness.choice(tuple(self._dynamic_pool[float]))
        return rand_value

    @property
    def random_string(self) -> str:
        """Provides a random string.

        Returns:
            A random string from the pool
        """
        assert self._dynamic_pool is not None
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
        assert self._dynamic_pool is not None
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
        assert self._dynamic_pool is not None
        self._dynamic_pool[str].add(value)
        method_name = "_add_value_for_" + name
        method = getattr(self, method_name)
        method(value)

    def _add_value_for_isalnum(self, value: str):
        assert self._dynamic_pool is not None
        if value.isalnum():
            self._dynamic_pool[str].add(value + "!")
        else:
            self._dynamic_pool[str].add("isalnum")

    def _add_value_for_islower(self, value: str):
        assert self._dynamic_pool is not None
        if value.islower():
            self._dynamic_pool[str].add(value.upper())
        else:
            self._dynamic_pool[str].add(value.lower())

    def _add_value_for_isupper(self, value: str):
        assert self._dynamic_pool is not None
        if value.isupper():
            self._dynamic_pool[str].add(value.lower())
        else:
            self._dynamic_pool[str].add(value.upper())

    def _add_value_for_isdecimal(self, value: str):
        assert self._dynamic_pool is not None
        if value.isdecimal():
            self._dynamic_pool[str].add("non_decimal")
        else:
            self._dynamic_pool[str].add("0123456789")

    def _add_value_for_isalpha(self, value: str):
        assert self._dynamic_pool is not None
        if value.isalpha():
            self._dynamic_pool[str].add(value + "1")
        else:
            self._dynamic_pool[str].add("isalpha")

    def _add_value_for_isdigit(self, value: str):
        assert self._dynamic_pool is not None
        if value.isdigit():
            self._dynamic_pool[str].add(value + "_")
        else:
            self._dynamic_pool[str].add("0")

    def _add_value_for_isidentifier(self, value: str):
        assert self._dynamic_pool is not None
        if value.isidentifier():
            self._dynamic_pool[str].add(value + "!")
        else:
            self._dynamic_pool[str].add("is_Identifier")

    def _add_value_for_isnumeric(self, value: str):
        assert self._dynamic_pool is not None
        if value.isnumeric():
            self._dynamic_pool[str].add(value + "A")
        else:
            self._dynamic_pool[str].add("012345")

    def _add_value_for_isprintable(self, value: str):
        assert self._dynamic_pool is not None
        if value.isprintable():
            self._dynamic_pool[str].add(value + "\n")
        else:
            self._dynamic_pool[str].add("is_printable")

    def _add_value_for_isspace(self, value: str):
        assert self._dynamic_pool is not None
        if value.isspace():
            self._dynamic_pool[str].add(value + "a")
        else:
            self._dynamic_pool[str].add("   ")

    def _add_value_for_istitle(self, value: str):
        assert self._dynamic_pool is not None
        if value.istitle():
            self._dynamic_pool[str].add(value + " AAA")
        else:
            self._dynamic_pool[str].add("Is Title")
