#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


class Example:
    def __init__(self, first: int, second: str) -> None:
        self._first = first
        self._second = second

    def first(self) -> int:
        return self._first

    @property
    def second(self) -> str:
        return self._second
