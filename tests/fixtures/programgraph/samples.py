#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def for_loop(sign, some_list):
    for index, mapping in enumerate(some_list):
        if sign in mapping:
            return index
