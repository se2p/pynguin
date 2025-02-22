#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
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
