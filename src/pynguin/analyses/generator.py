#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Handles type generator functions and their fitness values."""

from collections import defaultdict
from typing import TYPE_CHECKING

from pynguin.utils.orderedset import OrderedSet


if TYPE_CHECKING:
    from pynguin.analyses.typesystem import ProperType
    from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class GeneratorProvider:
    """Provides type generator functions and their fitness values."""

    def __init__(self):
        """Create a new generator provider."""
        self.generators: dict[ProperType, OrderedSet[GenericAccessibleObject]] = defaultdict(
            OrderedSet
        )
