#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def dummy():
    foo = "bar"  # noqa
    bar = 23  # noqa
    baz = 23.42  # noqa


class Dummy:
    _foo = "foo"
    _bar = 42
    _baz = 42.23
