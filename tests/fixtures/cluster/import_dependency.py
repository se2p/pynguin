#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from ast import Constant

import tests.fixtures.cluster.dependency as dep


def identity(obj: dep.SomeArgumentType) -> dep.SomeArgumentType:
    return obj


def bar(p: int) -> dep.SomeArgumentType:
    return dep.SomeArgumentType(p)


def ast_node() -> Constant:
    return Constant(value=42, kind=int)
