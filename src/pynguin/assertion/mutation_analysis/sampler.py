#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/utils.py.
"""
import random


class RandomSampler:
    def __init__(self, percentage: int) -> None:
        self.percentage = percentage if 0 < percentage < 100 else 100

    def is_mutation_time(self) -> bool:
        return random.randrange(100) < self.percentage
