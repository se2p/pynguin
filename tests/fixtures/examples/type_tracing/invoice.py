#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.examples.type_tracing.large_test_cluster import *  # noqa: F403,F401


def compute_sum(invoice: list[list[int]]) -> float | int:
    for element in invoice:
        element.append(42)
        element.append(18)
        if sum(element) > 100:
            return 42
        return 0
    return 1.0
