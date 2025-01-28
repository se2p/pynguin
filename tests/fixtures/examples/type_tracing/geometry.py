#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.examples.type_tracing.large_test_cluster import *  # noqa: F403,F401


def area(shape):
    if isinstance(shape, Square):  # noqa: F405
        return shape.a * shape.a
    if isinstance(shape, Circle):  # noqa: F405
        return (shape.r**2) * 3.14
    if hasattr(shape, "b"):
        return 0.5 * shape.b * shape.h
    return None
