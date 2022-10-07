#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from tests.fixtures.examples.type_tracing.large_test_cluster import *  # noqa: F403,F401


def compute_sum(invoice):
    summed = 0
    for item in invoice.elements:
        total = item.get_total()
        # Discount
        if total > 100:
            total *= 0.95
        summed += total
    return summed
