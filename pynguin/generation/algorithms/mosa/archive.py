#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides the archive for MOSA."""
import sys
from typing import Dict, Generic, Iterable, Set, TypeVar

import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff

F = TypeVar("F", bound=ff.FitnessFunction)  # pylint: disable=invalid-name
C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


class Archive(Generic[F, C]):
    """Implements the archive used by MOSA.

    The archive is used to store the shortest covering test cases found so far.  It
    also keeps track of which targets are yet to cover.

    For each objective of MOSA, the archive stores the chromosome which covers that
    objective.  Furthermore, when two chromosomes cover the same objective,
    the archive retains the smaller of the two, thus automatically optimising for the
    test case length as secondary criterion.

    It is imperative to know the best possible fitness value for a given fitness
    function.  Otherwise, the archive cannot determine whether or not the target has
    been reached.  Therefore, we limit ourselves to minimising fitness functions and
    assume 0.0 the best possible value.  This does not restrict generality as it is
    trivial to convert from maximising to minimising fitness functions.
    """

    def __init__(self, objectives: Set[F]) -> None:
        self._covered: Dict[F, C] = {}
        self._uncovered = set(objectives)
        self._objectives = objectives

    def update(self, solutions: Iterable[C]) -> None:
        """Updates this archive with the given set of solutions.

        In detail, when a solution manages to satisfy a previously uncovered target,
        it is stored in the archive.  If a target is already covered by one solution
        in the archive, and the given list contains another solution that covers the
        same target, the shorted of the two solutions is retained.  Otherwise,
        the solution is discarded.

        Args:
            solutions: The solutions to update the archive with
        """
        for objective in self._objectives:
            best_solution = self._covered.get(objective, None)
            best_size = sys.maxsize if best_solution is None else best_solution.size()

            for solution in solutions:
                fitness = solution.get_fitness_for(objective)
                size = solution.size()

                if fitness == 0.0 and size < best_size:
                    self._covered[objective] = solution
                    best_size = size
                    if objective in self._uncovered:
                        self._uncovered.remove(objective)

    @property
    def uncovered_goals(self) -> Set[F]:
        """Provides the set of goals that are yet to cover.

        Returns:
            The uncovered goals
        """
        return self._uncovered

    @property
    def covered_goals(self) -> Set[F]:
        """Provides the set of goals that are already covered.

        Returns:
            The covered goals
        """
        return set(self._covered.keys())

    @property
    def solutions(self) -> Set[C]:
        """Provides the best solutions found so far.

        Best solutions are those shortest test cases covering one of the targets
        managed by this archive.  Duplicates are eliminated.

        Returns:
            The best solutions in the archive
        """
        assert self._all_covered(), "Some covered targets have a fitness != 0.0"
        return set(self._covered.values())

    def reset(self) -> None:
        """Resets the archive."""
        self._uncovered.update(self._objectives)
        self._covered.clear()

    def _all_covered(self) -> bool:
        return all(
            [
                chromosome.get_fitness_for(fitness_function) == 0.0
                for fitness_function, chromosome in self._covered.items()
            ]
        )
