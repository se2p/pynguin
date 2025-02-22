#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a factory to create test case chromosomes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testcasechromosome as tcc

from pynguin.utils import randomness


if TYPE_CHECKING:
    import pynguin.ga.algorithms.archive as arch
    import pynguin.ga.computations as ff
    import pynguin.ga.testcasefactory as tcf
    import pynguin.testcase.testfactory as tf

    from pynguin.utils.orderedset import OrderedSet


class TestCaseChromosomeFactory(cf.ChromosomeFactory[tcc.TestCaseChromosome]):
    """A factory that creates test case chromosomes using the given test case factory.

    Also add the given fitness functions to the newly created test case chromosome.
    """

    def __init__(
        self,
        test_factory: tf.TestFactory,
        test_case_factory: tcf.TestCaseFactory,
        fitness_functions: OrderedSet[ff.TestCaseFitnessFunction],
    ) -> None:
        """Instantiates a new factory to create test case chromosomes.

        Args:
            test_factory: The internal factory required for the mutation.
            test_case_factory: The internal test case factory required for creation
                               of test cases.
            fitness_functions: The fitness functions that will be added to every
                               newly generated chromosome.
        """
        self._test_factory = test_factory
        self._test_case_factory = test_case_factory
        self._fitness_functions = fitness_functions

    def get_chromosome(self) -> tcc.TestCaseChromosome:  # noqa: D102
        test_case = self._test_case_factory.get_test_case()
        chrom = tcc.TestCaseChromosome(test_case=test_case, test_factory=self._test_factory)
        for func in self._fitness_functions:
            chrom.add_fitness_function(func)
        return chrom


class ArchiveReuseTestCaseChromosomeFactory(cf.ChromosomeFactory[tcc.TestCaseChromosome]):
    """Provides test case chromosomes from an archive with some probability.

    Otherwise, delegates to wrapped chromosome factory.
    """

    def __init__(  # noqa: D107
        self,
        delegate: cf.ChromosomeFactory[tcc.TestCaseChromosome],
        archive: arch.Archive,
    ):
        self._delegate = delegate
        self._archive = archive

    def get_chromosome(self) -> tcc.TestCaseChromosome:  # noqa: D102
        pick_from = self._archive.solutions
        if (
            len(pick_from) > 0
            and randomness.next_float()
            <= config.configuration.seeding.seed_from_archive_probability
        ):
            selected = randomness.choice(pick_from).clone()
            for _ in range(config.configuration.seeding.seed_from_archive_mutations):
                selected.mutate()
            return selected
        return self._delegate.get_chromosome()
