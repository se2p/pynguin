#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class Basket:
    items: list[str] = []

    def add_item(self, name: str):
        self.items.append(name)
