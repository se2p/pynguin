#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from tests.fixtures.examples.type_tracing.large_test_cluster import *  # noqa: F403,F401


def compute_sum(invoice):
    invoice.add(42)
    invoice.add(100)
    if sum(invoice) > 420:
        return 4
    return -1
