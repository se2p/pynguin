#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def for_loop(sign, some_list):
    for index, mapping in enumerate(some_list):
        if sign in mapping:
            return index
