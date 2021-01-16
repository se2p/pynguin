#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Instruments the bytecode to perform dynamic constant seeding."""
from __future__ import annotations

import logging
from typing import Optional, Set, cast, AnyStr, Dict, Union

from pynguin.utils import randomness


# pylint:disable=too-few-public-methods
class DynamicSeeding:
    """Provides the dynamic pool and methods to add values to and get values from the dynamic pool.

    The methods in this class are added to the module under test during an instruction phase before the main algorithm
    is executed. During this instruction phase, bytecode is added to the module under test which executes the methods
     adding values to the dynamic pool. The instrumentation is implemented in the module
     dynamicseedinginstrumentation.py.

    During the test generation process when a new value of one of the supported types is needed, this module provides
     methods to get values from the dynamic pool instead of randomly generating a new one.

    """

    # Variables for this types are stored in the dynamic pool.
    Types = Union[int, float, str]

    _logger = logging.getLogger(__name__)
    _instance: Optional[DynamicSeeding] = None
    _dynamic_pool: Optional[Dict[str, Set[Types]]] = None

    def __new__(cls) -> DynamicSeeding:
        if cls._instance is None:
            cls._instance = super(DynamicSeeding, cls).__new__(cls)
            cls._dynamic_pool = {
                "int": set(),
                "float": set(),
                "string": set()
            }
        return cls._instance

    @property
    def has_ints(self) -> bool:
        return self.has_constants("int")

    @property
    def has_floats(self) -> bool:
        return self.has_constants("float")

    @property
    def has_strings(self) -> bool:
        return self.has_constants("string")

    def has_constants(self, type_: str) -> bool:
        return len(self._dynamic_pool[type_]) > 0

    @property
    def random_int(self) -> int:
        rand_value = cast(int, randomness.choice(tuple(self._dynamic_pool["int"])))
        return rand_value

    @property
    def random_float(self) -> float:
        rand_value = cast(float, randomness.choice(tuple(self._dynamic_pool["float"])))
        return rand_value

    @property
    def random_string(self) -> AnyStr:
        rand_value = cast(str, randomness.choice(tuple(self._dynamic_pool["string"])))
        return rand_value

    def add_value(self, value: Types):
        """ Adds the given value to the corresponding set of the dynamic pool.

        Args:
            value: The value to add.
        """
        if isinstance(value, int):
            self._dynamic_pool["int"].add(value)
        elif isinstance(value, float):
            self._dynamic_pool["float"].add(value)
        elif isinstance(value, str):
            self._dynamic_pool["string"].add(value)
        else:
            pass

    def add_value_for_strings(self, value: str, name: str):
        if not isinstance(value, str):
            return
        self._dynamic_pool["string"].add(value)
        method_name = "_add_value_for_" + name
        method = getattr(self, method_name)
        method(value)

    def _add_value_for_isalnum(self, value: str):
        if value.isalnum():
            self._dynamic_pool["string"].add(value + "!")
        else:
            self._dynamic_pool["string"].add("isalnum")

    def _add_value_for_islower(self, value: str):
        if value.islower():
            self._dynamic_pool["string"].add(value.upper())
        else:
            self._dynamic_pool["string"].add(value.lower())

    def _add_value_for_isupper(self, value: str):
        if value.isupper():
            self._dynamic_pool["string"].add(value.lower())
        else:
            self._dynamic_pool["string"].add(value.upper())

    def _add_value_for_isdecimal(self, value: str):
        if value.isdecimal():
            self._dynamic_pool["string"].add("non_decimal")
        else:
            self._dynamic_pool["string"].add("0123456789")

    def _add_value_for_isalpha(self, value: str):
        if value.isalpha():
            self._dynamic_pool["string"].add(value + "1")
        else:
            self._dynamic_pool["string"].add("isalpha")

    def _add_value_for_isdigit(self, value: str):
        if value.isdigit():
            self._dynamic_pool["string"].add(value + "_")
        else:
            self._dynamic_pool["string"].add("0")

    def _add_value_for_isidentifier(self, value: str):
        if value.isidentifier():
            self._dynamic_pool["string"].add(value + "!")
        else:
            self._dynamic_pool["string"].add("is_Identifier")

    def _add_value_for_isnumeric(self, value: str):
        if value.isnumeric():
            self._dynamic_pool["string"].add(value + "A")
        else:
            self._dynamic_pool["string"].add("012345")

    def _add_value_for_isprintable(self, value: str):
        if value.isprintable():
            self._dynamic_pool["string"].add(value + "\n")
        else:
            self._dynamic_pool["string"].add("is_printable")

    def _add_value_for_isspace(self, value: str):
        if value.isspace():
            self._dynamic_pool["string"].add(value + "a")
        else:
            self._dynamic_pool["string"].add("   ")

    def _add_value_for_istitle(self, value: str):
        if value.istitle():
            self._dynamic_pool["string"].add(value + " AAA")
        else:
            self._dynamic_pool["string"].add("Is Title")
