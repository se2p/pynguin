#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Instruments the bytecode to perform dynamic constant seeding."""
from __future__ import annotations

import logging
import re
from typing import Optional, Set, cast, AnyStr, Dict, Union, Any

from pynguin.utils import randomness


# pylint:disable=too-few-public-methods
class DynamicSeeding:
    """Instruments code objects to enable dynamic constant seeding.

    Supported is collecting values of the types int, float and string.

    Instrumented are the common compare operations (==, !=, <, >, <=, >=) and the string methods contained in the
    STRING_FUNCTION_NAMES list. This means, if one of the above operations and methods is used in an if-conditional,
     corresponding values are added to the dynamic constant pool.

    General notes:

    When calling a method on an object, the arguments have to be on top of the stack.
    In most cases, we need to rotate the items on the stack with ROT_THREE or ROT_FOUR
    to reorder the elements accordingly.

    A POP_TOP instruction is required after calling a method, because each method
    implicitly returns None."""

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

    def add_value_for_isalnum(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isalnum():
            self._dynamic_pool["string"].add(value + "!")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isalnum())
            value_as_alnum = value.translate({delchars: None})
            self._dynamic_pool["String"].add(value_as_alnum)
