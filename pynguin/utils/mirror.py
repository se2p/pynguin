#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""A simple mirror dict."""


class Mirror(dict):
    """A dictionary that returns each key as its value.
    e.g.
    mirror = Mirror()
    assert mirror[5] == 5
    """

    def __missing__(self, item):
        self[item] = item
        return item
