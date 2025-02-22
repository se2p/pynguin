#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# flake8: noqa
class NoPrimitive:
    pass


def seed_test_case_1():
    # needed to check if instantiation is handled properly
    var0 = NoPrimitive()
