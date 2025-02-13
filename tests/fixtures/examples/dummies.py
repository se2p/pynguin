#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class Dummy:
    def __init__(self, x: int) -> None:
        self._x = x

    def get_x(self) -> int:
        return self._x
