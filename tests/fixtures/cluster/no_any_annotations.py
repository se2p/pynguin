#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import Any


def foo(a, b: object, c: Any):
    return a, b, c


def bar() -> Any:
    return foo


def baz() -> object:
    return bar


def faz() -> None:
    pass
