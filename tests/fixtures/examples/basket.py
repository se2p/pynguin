#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import List


class Basket:
    items: List[str] = []

    def add_item(self, name: str):
        self.items.append(name)
