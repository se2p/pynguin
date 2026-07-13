#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def public_function(x: int) -> int:
    return x


def _protected_function(x: int) -> int:
    return x


def __private_function(x: int) -> int:
    return x


class PublicClass:
    def __init__(self, value: int) -> None:
        self._value = value

    def public_method(self, x: int) -> int:
        return x

    def _protected_method(self, x: int) -> int:
        return x

    def __private_method(self, x: int) -> int:
        return x


class _ProtectedClass:
    def __init__(self, value: int) -> None:
        self._value = value

    def public_method(self, x: int) -> int:
        return x
