#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


class Basket:
    items: list[str] = []

    def add_item(self, name: str):
        self.items.append(name)
