#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def _private_method(a: int, b: int) -> int:
    return a + b


class Dummy:
    @staticmethod
    def _private(self, x: int) -> int:
        return x
