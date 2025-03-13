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


class _Generator(Selectable):
    """Allows selecting a generator based on its fitness value for a type to generate.

    To calculate the fitness value, we need to have the generator, the type to generate,
    and a fitness function. The subtype distance can be calculated during the fitness
    calculation or be provided directly.
    """

    def __init__(
        self,
        generator: GenericAccessibleObject,
        type_to_generate: ProperType,
        fitness_function: GeneratorFitnessFunction,
        subtype_distance: int | None = None,
    ):
        """Create a new generator.

        Args:
            generator: The generator to select.
            type_to_generate: The type to generate.
            fitness_function: The fitness function to use.
            subtype_distance: The subtype distance between the type to generate and the
                generated type.
        """
        self._generator = generator
        self._type_to_generate = type_to_generate
        self._fitness_function = fitness_function
        self._subtype_distance = subtype_distance

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
            fitness_function: The fitness function to use.
        """
        # Can only be GenericEnum, as only GenericCallableAccessibleObjects and
        # GenericEnums are added as generators
        if not isinstance(self._generator, GenericCallableAccessibleObject):
            return 0.0

        fitness = fitness_function.compute_fitness(
            self._type_to_generate, self._generator, self._subtype_distance
        )
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
        selection_function: SelectionFunction[_Generator],
    ):
        """Create a new generator provider.

        Args:
            type_system: The type system to use.
            selection_function: The selection function to use.
        """
        self._generators: dict[ProperType, OrderedSet[GenericAccessibleObject]] = defaultdict(
            OrderedSet
        )
        self._type_system = type_system
        self._fitness_function: GeneratorFitnessFunction = HeuristicGeneratorFitnessFunction(
            type_system
        )
        self._selection_function: SelectionFunction[_Generator] = selection_function

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
        self, type_generators: FrozenOrderedSet[_Generator]
    ) -> OrderedSet[_Generator]:
        # TODO: Filter for fitness > 0.0 needed?
        return OrderedSet(sorted(type_generators, key=lambda x: x.get_fitness()))

    def _select_generator(
        self, type_generators: FrozenOrderedSet[_Generator]
    ) -> GenericAccessibleObject:
        """Select a generator from a set of generators.

        Compared to random selection this adds an overhead by computing a fitness value
        for each generator and sorting them. We can cache both operations so the overhead
        is mostly limited to the first iteration.

        Args:
            type_generators: The set of generators to select from.

        Returns:
            The selected generator.
        """
        generator_objects = self._sorted_generators(type_generators)
        # As builtins.object is a superclass of all classes, we can be sure that
        # there is always at least one generator available
        selected = self._selection_function.select(list(generator_objects))[0]
        return selected.generator

    @functools.lru_cache(maxsize=1024)
    def _get_generators_for(self, typ: ProperType) -> OrderedSet[_Generator]:
        """Get all generators for a specific type."""
        if isinstance(typ, AnyType):
            # Just take everything when it's Any.
            return self._get_all_generators(typ)

        if typ.accept(is_primitive_type):
            return OrderedSet()

        generated_types = self.get_all_types()
        generators: OrderedSet[_Generator] = OrderedSet()
        for generated_typ in generated_types:
            distance = self._type_system.subtype_distance(typ, generated_typ)
            if distance is not None:
                generator_methods = self.get_for_type(generated_typ)
                for generator_method in generator_methods:
                    generators.add(
                        _Generator(
                            generator_method, generated_typ, self._fitness_function, distance
                        )
                    )

        return generators

    def _get_all_generators(self, typ: ProperType) -> OrderedSet[_Generator]:
        all_generators = itertools.chain.from_iterable(self.get_all().values())
        return OrderedSet(
            _Generator(generator, typ, self._fitness_function) for generator in all_generators
        )

    def select_generator_for(self, parameter_type: ProperType) -> GenericAccessibleObject | None:
        """Select a generator for a specific type.

        Args:
            parameter_type: The type to select a generator for.

        Returns:
            The selected generator.
        """
        type_generators = self._get_generators_for(parameter_type)
        if type_generators:
            return self._select_generator(type_generators.freeze())
        return None

    def clear_generator_cache(self):
        """Clear the generator cache."""
        self._get_generators_for.cache_clear()
        self._sorted_generators.cache_clear()
