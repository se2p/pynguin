#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def _private_method(a: int, b: int) -> int:
    return a + b


class Dummy:
    @staticmethod
    def _private(self, x: int) -> int:
        return x
