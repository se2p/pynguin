#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an implementation for a test suite chromosome"""
from __future__ import annotations

import pynguin.testsuite.abstracttestsuitechromosome as atsc


# pylint:disable=too-many-instance-attributes
class TestSuiteChromosome(atsc.AbstractTestSuiteChromosome):
    """Provides an implementation for a test suite chromosome"""

    def clone(self) -> TestSuiteChromosome:
        chromosome = TestSuiteChromosome()

        for test in self._tests:
            chromosome.add_test(test.clone())

        chromosome._current_values = dict(self._current_values)
        chromosome._fitness_functions = list(self._fitness_functions)
        chromosome._changed = self._changed
        chromosome._test_case_factory = self._test_case_factory
        return chromosome
