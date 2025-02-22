#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def test_case0():
    var0 = 10
    var1 = 12
    assert var1 == var0


def test_case1():
    var0 = -1
    assert var0 == -1


def test_case2():
    var0 = True
    assert var0 is not False


def test_case3():
    var0 = None
    assert var0 is None
