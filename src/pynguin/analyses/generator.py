#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Handles type generator functions and their fitness values."""

from collections import defaultdict

from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import NoneType
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import TypeSystem
from pynguin.analyses.typesystem import is_primitive_type
from pynguin.ga.chromosome import Selectable
from pynguin.ga.computations import GeneratorFitnessFunction
from pynguin.ga.computations import HeuristicGeneratorFitnessFunction
from pynguin.ga.operators.selection import SelectionFunction
from pynguin.ga.operators.selection import TournamentSelection
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.orderedset import OrderedSet


class Generator(Selectable):
    """Represents a generator function for a specific type."""

    def __init__(
        self,
        generator: GenericAccessibleObject,
        generated_type: ProperType,
        fitness_function: GeneratorFitnessFunction,
    ):
        """Create a new generator."""
        self._generator = generator
        self._generated_type = generated_type
        self._fitness_function = fitness_function

    @property
    def generator(self) -> GenericAccessibleObject:
        """Get the generator function."""
        return self._generator

    def get_fitness(self) -> float:
        """Get the fitness value of this generator."""
        return self.get_fitness_for(self._fitness_function)

    def get_fitness_for(self, fitness_function: GeneratorFitnessFunction) -> float:
        """Get the fitness value of this generator for a specific fitness function.

        Args:
            fitness_function: The fitness function to consider.
        """
        if isinstance(self._generated_type, Instance):
            return fitness_function.compute_fitness(self._generated_type.type, self._generator)
        return 20  # TODO: Adjust, return bad value

    def __str__(self):
        return str(self._generator)

    def __repr__(self):
        return self.__str__()


class GeneratorProvider:
    """Provides type generator functions and their fitness values."""

    def __init__(self, type_system: TypeSystem) -> None:
        """Create a new generator provider.

        Args:
            type_system: The type system to use.
        """
        self._generators: dict[ProperType, OrderedSet[GenericAccessibleObject]] = defaultdict(
            OrderedSet
        )
        self._fitness_function: GeneratorFitnessFunction = HeuristicGeneratorFitnessFunction(
            type_system
        )
        self._selection_function: SelectionFunction[Generator] = TournamentSelection()

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
        self._generators.pop(proper_type)

    def add_for_type(
        self, proper_type: ProperType, generator: GenericCallableAccessibleObject
    ) -> None:
        """Add a set of generators for a specific type.

        Args:
            proper_type: The type to add the generators for.
            generator: The generator to add.
        """
        self._generators[proper_type].add(generator)

    def select_generator(
        self, parameter_type: ProperType, type_generators: OrderedSet[GenericAccessibleObject]
    ) -> GenericAccessibleObject:
        """Select a generator from a set of generators.

        Args:
            parameter_type: The type to select a generator for.
            type_generators: The set of generators to select from.

        Returns:
            The selected generator.
        """
        generator_objects = [
            Generator(gen, parameter_type, self._fitness_function) for gen in type_generators
        ]
        generator_objects.sort(key=lambda g: g.get_fitness(), reverse=True)
        return generator_objects[0].generator if generator_objects else type_generators[0]
