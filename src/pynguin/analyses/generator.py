#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Handles type generator functions and their fitness values."""

from collections import defaultdict

from pynguin.analyses.typesystem import NoneType
from pynguin.analyses.typesystem import ProperType
from pynguin.analyses.typesystem import is_primitive_type
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.orderedset import OrderedSet


class GeneratorProvider:
    """Provides type generator functions and their fitness values."""

    def __init__(self):
        """Create a new generator provider."""
        self._generators: dict[ProperType, OrderedSet[GenericAccessibleObject]] = defaultdict(
            OrderedSet
        )

    def add(self, generator: GenericAccessibleObject) -> None:
        """Add a new generator.

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
        return self._generators.get(proper_type)

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
