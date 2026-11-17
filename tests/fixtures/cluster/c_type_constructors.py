#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Uses classes whose constructors are implemented in C."""

import datetime
from decimal import Decimal
from types import SimpleNamespace as Namespace


class OwnDate(datetime.date):
    """A Python subclass that inherits the C constructor of date."""


class PythonInit:
    def __init__(self, value: int) -> None:
        self.value = value


class Outer:
    class Inner:
        pass


def use_date(d: datetime.date) -> str:
    if d.month == 2:
        return "feb"
    return "other"


def use_decimal(q: Decimal) -> str:
    if q > 10:
        return "big"
    return "small"


def use_namespace(n: Namespace) -> bool:
    return hasattr(n, "x")


def use_own_date(d: OwnDate, p: PythonInit, i: Outer.Inner) -> int:
    return d.day + p.value
