#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class Plus:
    calculations = 0

    def plus_three(self, number):
        self.calculations += 1
        return number + 3

    def plus_four(self, number):
        self.calculations += 1
        return number + 4
