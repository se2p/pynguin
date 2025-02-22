#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""A simple mirror dict."""


class Mirror(dict):  # noqa: FURB189
    """A dictionary that returns each key as its value.

    >>> mirror = Mirror()
    >>> assert mirror[5] == 5.
    """

    def __missing__(self, item):
        self[item] = item
        return item
