#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


class Human:
    def __init__(self, name: str) -> None:
        self._name = name

    def __str__(self):
        return super().__str__()

    def get_name(self) -> str:
        return self._name
