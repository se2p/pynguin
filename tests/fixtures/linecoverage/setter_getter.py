#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class SetterGetter:
    attribute = 0

    def setter(self, new_value) -> None:
        self.attribute = new_value

    def getter(self) -> int:
        return self.attribute
