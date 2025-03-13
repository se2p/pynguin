#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Handles type generator functions.

Generators can be either GenericCallableAccessibleObjects or GenericEnum objects.
"""

import functools
import itertools

from collections import defaultdict

from pynguin.analyses.typesystem import AnyType
from pynguin.analyses.typesystem import NoneType
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TypeSystem
from pynguin.analyses.typesystem import is_primitive_type
from pynguin.ga.chromosome import Selectable
from pynguin.ga.computations import GeneratorFitnessFunction
from pynguin.ga.computations import HeuristicGeneratorFitnessFunction
from pynguin.ga.operators.selection import SelectionFunction
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.orderedset import FrozenOrderedSet
from pynguin.utils.orderedset import OrderedSet


class Generator(Selectable):
    """Represents a generator function for a specific type."""

    def __init__(
        self,
        generator: GenericAccessibleObject,
        type_to_generate: ProperType,
        fitness_function: GeneratorFitnessFunction,
    ):
        """Create a new generator."""
        self.fitness: float | None = None
        self._generator = generator
        self._type_to_generate = type_to_generate
        self._fitness_function = fitness_function

    @property
    def generator(self) -> GenericAccessibleObject:
        """Get the generator function."""
        return self._generator

    def get_fitness(self) -> float:
        """Get the fitness value of this generator."""
        if self.fitness is not None:
            return self.fitness
        self.fitness = self.get_fitness_for(self._fitness_function)
        return self.fitness

    def get_fitness_for(self, fitness_function: GeneratorFitnessFunction) -> float:
        """Get the fitness value of this generator for a specific fitness function.

        Args:
            fitness_function: The fitness function to consider.
        """
        # Can only be GenericEnum, as only GenericCallableAccessibleObjects and
        # GenericEnums are added as generators
        if not isinstance(self._generator, GenericCallableAccessibleObject):
            return 0.0

        fitness = fitness_function.compute_fitness(self._type_to_generate, self._generator)
        return fitness if fitness is not None else -1

    def __str__(self):
        return str(self._generator)

    def __repr__(self):
        return self.__str__()


class GeneratorProvider:
    """Provides type generator functions and their fitness values."""

    def __init__(
        self,
        type_system: TypeSystem,
        selection_function: SelectionFunction[Generator],
    ):
        """Create a new generator provider.

        Args:
            type_system: The type system to use.
            selection_function: The selection function to use.
        """
        self._generators: dict[ProperType, OrderedSet[GenericAccessibleObject]] = defaultdict(
            OrderedSet
        )
        self._fitness_function: GeneratorFitnessFunction = HeuristicGeneratorFitnessFunction(
            type_system
        )
        self._selection_function: SelectionFunction[Generator] = selection_function

    def add(self, generator: GenericAccessibleObject) -> None:
        """Add a new generator.

        The return type might be AnyType.

        Args:
            generator: The generator to add.
        """
        generated_type = generator.generated_type()
        if isinstance(generated_type, NoneType) or generated_type.accept(is_primitive_type):
            return
        self._generators[generated_type].add(generator)

    def get_all(self) -> dict[ProperType, OrderedSet[GenericAccessibleObject]]:
        """Get all generators."""
        return self._generators

    def get_all_types(self) -> OrderedSet[ProperType]:
        """Get all types for which generators are available."""
        return OrderedSet(self._generators.keys())

    def get_for_type(self, proper_type: ProperType) -> OrderedSet[GenericAccessibleObject]:
        """Get all generators for a specific type.

        Args:
            proper_type: The type to get the generators for.

        Returns:
            The generators for the given type.
        """
        return self._generators.get(proper_type, OrderedSet())

    def remove_all_generators_for(self, proper_type: ProperType) -> None:
        """Remove all generators for a specific type.

        Args:
            proper_type: The type to remove the generators for.
        """
        del self._generators[proper_type]

    def add_for_type(
        self, proper_type: ProperType, generator: GenericCallableAccessibleObject
    ) -> None:
        """Add a set of generators for a specific type.

        Args:
            proper_type: The type to add the generators for.
            generator: The generator to add.
        """
        self._generators[proper_type].add(generator)

    @functools.lru_cache(maxsize=1024)
    def _sorted_generators(
        self, parameter_type: ProperType, type_generators: FrozenOrderedSet[GenericAccessibleObject]
    ) -> list[Generator]:
        generators = [
            Generator(gen, parameter_type, self._fitness_function) for gen in type_generators
        ]
        generators = [gen for gen in generators if gen.get_fitness() >= 0.0]
        generators.sort(key=lambda x: x.get_fitness())
        return generators

    def select_generator(
        self, parameter_type: ProperType, type_generators: FrozenOrderedSet[GenericAccessibleObject]
    ) -> GenericAccessibleObject:
        """Select a generator from a set of generators.

        Compared to random selection this adds an overhead by computing a fitness value
        for each generator and sorting them. We can cache both operations so the overhead
        is mostly limited to the first iteration.

        Args:
            parameter_type: The type to select a generator for.
            type_generators: The set of generators to select from.

        Returns:
            The selected generator.
        """
        generator_objects = self._sorted_generators(parameter_type, type_generators)
        # As builtins.object is a superclass of all classes, we can be sure that
        # there is always at least one generator available
        selected = self._selection_function.select(generator_objects)[0]
        return selected.generator

    @functools.lru_cache(maxsize=1024)
    def get_generators_for(  # noqa: D102
        self, typ: ProperType
    ) -> OrderedSet[GenericAccessibleObject]:
        if isinstance(typ, AnyType):
            # Just take everything when it's Any.
            return OrderedSet(itertools.chain.from_iterable(self.get_all().values()))

        if typ.accept(is_primitive_type):
            return OrderedSet()

        generators = OrderedSet(itertools.chain.from_iterable(self.get_all().values()))
        sorted_generators = self._sorted_generators(typ, generators.freeze())
        return OrderedSet([gen.generator for gen in sorted_generators])

    def select_generator_for(self, parameter_type: ProperType) -> GenericAccessibleObject | None:
        """Select a generator for a specific type.

        Args:
            parameter_type: The type to select a generator for.

        Returns:
            The selected generator.
        """
        type_generators = self.get_generators_for(parameter_type)
        if type_generators:
            return self.select_generator(parameter_type, type_generators.freeze())
        return None
