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
        if not isinstance(value, str):
            return
        self._dynamic_pool["string"].add(value)
        if value.isalnum():
            self._dynamic_pool["string"].add(value + "!")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isalnum())
            value_as_alnum = value.translate({delchars: None})
            if value_as_alnum is not None:
                self._dynamic_pool["String"].add(value_as_alnum)
            else:
                self._dynamic_pool["String"].add("is_alnum")

    def add_value_for_islower(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.islower():
            self._dynamic_pool["string"].add(value.upper())
        else:
            self._dynamic_pool["string"].add(value.lower())

    def add_value_for_isupper(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isupper():
            self._dynamic_pool["string"].add(value.lower())
        else:
            self._dynamic_pool["string"].add(value.upper())

    def add_value_for_isdecimal(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isdecimal():
            self._dynamic_pool["string"].add("non_decimal")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isdecimal())
            value_as_decimal = value.translate({delchars: None})
            if value_as_decimal is not None:
                self._dynamic_pool["string"].add(value_as_decimal)
            else:
                self._dynamic_pool["string"].add("0123456789")

    def add_value_for_isalpha(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isalpha():
            self._dynamic_pool["string"].add(value + "1")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isalpha())
            value_as_alpha = value.translate({delchars: None})
            if value_as_alpha is not None:
                self._dynamic_pool["string"].add(value_as_alpha)
            else:
                self._dynamic_pool["string"].add("isalpha")

    def add_value_for_isdigit(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isdigit():
            self._dynamic_pool["string"].add(value + "_")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isdigit())
            value_as_digit = value.translate({delchars: None})
            if value_as_digit is not None:
                self._dynamic_pool["string"].add(value_as_digit)
            else:
                self._dynamic_pool["string"].add("0")

    def add_value_for_isidentifier(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isidentifier():
            self._dynamic_pool["string"].add(value + "!")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isidentifier())
            value_as_identifier = value.translate({delchars: None})
            if value_as_identifier is not None:
                self._dynamic_pool["string"].add(value_as_identifier)
            else:
                self._dynamic_pool["string"].add("is_Identifier")

    def add_value_for_isnumeric(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isnumeric():
            self._dynamic_pool["string"].add(value + "A")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isnumeric())
            value_as_numeric = value.translate({delchars: None})
            if value_as_numeric is not None:
                self._dynamic_pool["string"].add(value_as_numeric)
            else:
                self._dynamic_pool["string"].add("012345")

    def add_value_for_isprintable(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isprintable():
            self._dynamic_pool["string"].add(value + "\n")
        else:
            delchars = ''.join(c for c in map(chr, range(256)) if not c.isprintable())
            value_as_printable = value.translate({delchars: None})
            if value_as_printable is not None:
                self._dynamic_pool["string"].add(value_as_printable)
            else:
                self._dynamic_pool["string"].add("is_printable")

    def add_value_for_isspace(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.isspace():
            self._dynamic_pool["string"].add(value + "a")
        else:
            self._dynamic_pool["string"].add("   ")

    def add_value_for_istitle(self, value: str):
        self._dynamic_pool["string"].add(value)
        if value.istitle():
            self._dynamic_pool["string"].add(value + " AAA")
        else:
            self._dynamic_pool["string"].add("Is Title")

