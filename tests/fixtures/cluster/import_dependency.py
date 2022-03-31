#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import tests.fixtures.cluster.dependency as dep


def identity(obj: dep.SomeArgumentType) -> dep.SomeArgumentType:
    return obj


def bar(p: int) -> dep.SomeArgumentType:
    return dep.SomeArgumentType(p)
