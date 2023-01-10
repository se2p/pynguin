#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# flake8: noqa
class NoPrimitive:
    pass


def seed_test_case_1():
    # needed to check if instantiation is handled properly
    var0 = NoPrimitive()
