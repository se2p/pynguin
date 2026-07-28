#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixture whose objects execute module code while they are being unpickled."""


class UnpicklingError(Exception):
    """An exception whose reconstruction runs instrumented module code."""

    def __init__(self, value: int):  # noqa: D107
        super().__init__(value)
        self.value = value


def raise_error(value: int) -> None:
    """Raise an exception that runs module code when it is unpickled.

    Args:
        value: The value carried by the exception.

    Raises:
        UnpicklingError: Always.
    """
    raise UnpicklingError(value)
