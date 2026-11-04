#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class SomeArgumentType:
    def __init__(self, needed_for_me: int):
        pass

    # needed so the cluster creates at least one modifier for this class
    def addOne(self, x: int) -> int:
        return x + 1
