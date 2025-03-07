#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Handles type generator functions and their fitness values."""

from collections import defaultdict
from typing import TYPE_CHECKING

from pynguin.analyses.typesystem import NoneType
from pynguin.analyses.typesystem import is_primitive_type
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
from pynguin.utils.orderedset import OrderedSet


if TYPE_CHECKING:
    from pynguin.analyses.typesystem import ProperType


class GeneratorProvider:
    """Provides type generator functions and their fitness values."""

    def __init__(self):
        """Create a new generator provider."""
        self.generators: dict[ProperType, OrderedSet[GenericAccessibleObject]] = defaultdict(
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
        self.generators[generated_type].add(generator)
