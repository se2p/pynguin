#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""A dummy module to be used as a test fixture."""


def dummy():
    """A dummy method in the test fixture."""
    foo = "bar"  # noqa
    bar = 23  # noqa
    baz = 42.23  # noqa


class Dummy:
    """A dummy class in the test fixture."""

    _foo = "foo"
    _bar = 42
    _baz = 42.23
