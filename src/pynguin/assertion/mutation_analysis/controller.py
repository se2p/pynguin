#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a controller for generating mutants."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.assertion.mutation_analysis.strategies as ms
import pynguin.configuration as config
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer, create_module
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.timeout import TestExecutionTimeoutError

if TYPE_CHECKING:
    import types
    from collections.abc import Generator
    from types import ModuleType

    from pynguin.assertion.mutation_analysis.operators.base import (
        Mutation,
        MutationOperator,
    )


_LOGGER = logging.getLogger(__name__)

_strategies: dict[config.MutationStrategy, type[ms.HOMStrategy]] = {
    config.MutationStrategy.FIRST_TO_LAST: ms.FirstToLastHOMStrategy,
    config.MutationStrategy.BETWEEN_OPERATORS: ms.BetweenOperatorsHOMStrategy,
    config.MutationStrategy.RANDOM: ms.RandomHOMStrategy,
    config.MutationStrategy.EACH_CHOICE: ms.EachChoiceHOMStrategy,
}


@dataclasses.dataclass
class MutationMetrics:
    """Stores metrics from mutation analysis."""

    num_created_mutants: int
    num_killed_mutants: int
    num_timeout_mutants: int

    def get_score(self) -> float | None:
        """Computes the mutation score.

        Returns:
            The mutation score, or ``None`` if no checked mutant contributed
            usable information (every created mutant timed out), in which case
            the score is unmeasurable rather than vacuously perfect.
        """
        divisor = self.num_created_mutants - self.num_timeout_mutants
        assert divisor >= 0
        if divisor == 0:
            if self.num_created_mutants == 0:
                # No mutants were created -> vacuously covered.
                return 1.0
            # Every created mutant timed out; we learned nothing about the
            # assertions, so the score cannot be measured.
            return None
        return self.num_killed_mutants / divisor


def compute_reported_mutation_score(metrics: MutationMetrics, num_created: int) -> float | None:
    """Computes the mutation score to report, given the pre-truncation mutant count.

    Args:
        metrics: The metrics over the checked mutants.
        num_created: The number of mutants the module yielded, checked or not.

    Returns:
        The mutation score, or ``None`` if mutants were created but none of them
        could be checked (e.g., every mutant was an invalid module), in which case
        the score is unmeasurable rather than vacuously perfect.
    """
    if num_created > 0 and metrics.num_created_mutants == 0:
        return None
    return metrics.get_score()


def setup_mutant_generator() -> mu.Mutator:
    """Set up the mutant generator based on configuration.

    Returns:
        The configured mutant generator.

    Raises:
        ConfigurationException: If the mutation strategy or order is invalid.
    """
    operators: list[type[MutationOperator]] = [
        *mo.standard_operators,
        *mo.experimental_operators,
    ]

    output = config.configuration.test_case_output
    mutation_strategy = output.mutation_strategy

    if mutation_strategy == config.MutationStrategy.FIRST_ORDER_MUTANTS:
        # Reorder (interleave + defer timeout-prone operators) whenever a bound on
        # the mutation-analysis phase is active, so truncation stays fair.
        reorder = output.maximum_mutants >= 0 or output.maximum_mutation_time >= 0
        return mu.FirstOrderMutator(
            operators,
            maximum_mutants=output.maximum_mutants,
            sampling_seed=config.configuration.seeding.seed,
            reorder=reorder,
        )

    order = config.configuration.test_case_output.mutation_order

    if order <= 0:
        raise ConfigurationException("Mutation order should be > 0.")

    if mutation_strategy in _strategies:
        hom_strategy = _strategies[mutation_strategy](order)
        return mu.HighOrderMutator(operators, hom_strategy=hom_strategy)

    raise ConfigurationException("No suitable mutation strategy found.")


def create_mutation_controller(module: types.ModuleType) -> MutationController:
    """Create a MutationController for the specified module.

    Args:
        module: The module to mutate.

    Returns:
        The configured MutationController.
    """
    try:
        module_source_code = inspect.getsource(module)
    except Exception:
        file_path = getattr(module, "__file__", None)
        if file_path:
            module_source_code = Path(file_path).read_text(encoding="utf-8")
        else:
            raise
    module_ast = ParentNodeTransformer.create_ast(module_source_code)
    mutant_generator = setup_mutant_generator()
    return MutationController(mutant_generator, module_ast, module)


class MutationController:
    """A controller that creates mutants."""

    def __init__(
        self,
        mutant_generator: mu.Mutator,
        module_ast: ast.Module,
        module: types.ModuleType,
    ) -> None:
        """Initialize the controller.

        Args:
            mutant_generator: The mutant generator to use.
            module_ast: The AST of the module to mutate.
            module: The module to mutate.
        """
        self._mutant_generator = mutant_generator
        self._module_ast = module_ast
        self._module = module

    def create_mutant(self, mutant_ast: ast.Module) -> ModuleType:
        """Creates a mutant of the module.

        Args:
            mutant_ast: The mutant AST.

        Returns:
            The created mutant module.
        """
        return create_module(mutant_ast, self._module.__name__, self._module)

    def create_mutants(
        self,
    ) -> Generator[tuple[ModuleType | None, list[Mutation]]]:
        """Creates mutants for the module.

        Returns:
            A generator of tuples where the first entry is the mutated module or None
            if the mutated module cannot be created and the second part is a list of
            all the mutations operators applied.
        """
        for mutations, mutant_ast in self._mutant_generator.mutate(self._module_ast, self._module):
            assert isinstance(mutant_ast, ast.Module)

            try:
                mutant_module = self.create_mutant(mutant_ast)
            except Exception as exception:  # noqa: BLE001
                _LOGGER.debug("Error creating mutant: %s", exception)
                mutant_module = None
            except SystemExit as exception:
                _LOGGER.debug("Caught SystemExit during mutant creation/execution: %s", exception)
                mutant_module = None
            except TestExecutionTimeoutError as exception:
                _LOGGER.warning("Caught timeout during mutant creation/execution: %s", exception)
                mutant_module = None

            yield mutant_module, mutations

    def mutant_count(self) -> int:
        """Calculates the number of mutants that can be created.

        This is the pre-truncation total: if the mutant generator is configured
        to sample a subset (e.g. via a mutant-count cap), this still reports the
        full number of mutations the module yields.

        Returns:
            The number of mutants that can be created.
        """
        return self._mutant_generator.mutation_count(self._module_ast, self._module)
