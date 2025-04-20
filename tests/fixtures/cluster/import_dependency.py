#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast

import tests.fixtures.cluster.dependency as dep


def identity(obj: dep.SomeArgumentType) -> dep.SomeArgumentType:
    return obj


def bar(p: int) -> dep.SomeArgumentType:
    return dep.SomeArgumentType(p)


def ast_node() -> ast.Constant:
    return ast.Constant(value=42, kind=int)
