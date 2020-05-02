# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides a test cluster."""
from __future__ import annotations
from typing import Type, Set, Dict, cast, Optional, Any, List

from typing_inspect import is_union_type, get_args

from pynguin.utils import randomness, type_utils
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject
from pynguin.utils.type_utils import PRIMITIVES


class TestCluster:
    """A test cluster which contains all methods/constructors/functions
    and all required transitive dependencies.
    """

    def __init__(self):
        """Create new test cluster."""
        self._generators: Dict[Type, Set[GenericAccessibleObject]] = cast(
            Dict[Type, Set[GenericAccessibleObject]], dict()
        )
        self._modifiers: Dict[Type, Set[GenericAccessibleObject]] = cast(
            Dict[Type, Set[GenericAccessibleObject]], dict()
        )
        self._accessible_objects_under_test: Set[GenericAccessibleObject] = set()

    def add_generator(self, generator: GenericAccessibleObject) -> None:
        """Add the given accessible as a generator, if the type is known, not primitive
         and not NoneType."""
        type_ = generator.generated_type()
        if (
            type_ is None
            or type_utils.is_none_type(type_)
            or type_utils.is_primitive_type(type_)
        ):
            return
        if type_ in self._generators:
            self._generators[type_].add(generator)
        else:
            self._generators[type_] = {generator}

    def add_accessible_object_under_test(self, obj: GenericAccessibleObject):
        """Add accessible object to the objects under test."""
        self._accessible_objects_under_test.add(obj)

    def add_modifier(self, type_: Type, obj: GenericAccessibleObject):
        """Add a modifier, e.g. something that can be used to modify the given type.
        e.g. a method."""
        if type_ in self._modifiers:
            self._modifiers[type_].add(obj)
        else:
            self._modifiers[type_] = {obj}

    @property
    def accessible_objects_under_test(self) -> Set[GenericAccessibleObject]:
        """Provides all accessible objects that are under test."""
        return self._accessible_objects_under_test

    def num_accessible_objects_under_test(self) -> int:
        """Provide the number of accessible objects under test.
        This is useful to check if there even is something to test."""
        return len(self._accessible_objects_under_test)

    def get_generators_for(self, for_type: Type) -> Set[GenericAccessibleObject]:
        """
        Retrieve all known generators for the given type which are
        known within the test cluster.
        """
        if for_type in self._generators:
            return self._generators[for_type]
        return set()

    def get_modifiers_for(self, for_type: Type) -> Set[GenericAccessibleObject]:
        """Get all known modifiers of a type. This currently does not take
        inheritance into account."""
        if for_type in self._modifiers:
            return self._modifiers[for_type]
        return set()

    @property
    def generators(self) -> Dict[Type, Set[GenericAccessibleObject]]:
        """Provides all available generators."""
        return self._generators

    @property
    def modifiers(self) -> Dict[Type, Set[GenericAccessibleObject]]:
        """Provides all available modifiers."""
        return self._modifiers

    def get_random_accessible(self) -> Optional[GenericAccessibleObject]:
        """Provide a random accessible of the unit under test."""
        if self.num_accessible_objects_under_test() == 0:
            return None
        return randomness.choice(list(self._accessible_objects_under_test))

    def get_random_call_for(self, type_: Type) -> GenericAccessibleObject:
        """Get a random modifier for the given type."""
        accessible_objects = self.get_modifiers_for(type_)
        if len(accessible_objects) == 0:
            raise ConstructionFailedException("No modifiers for " + str(type_))
        return randomness.choice(list(accessible_objects))

    def get_all_generatable_types(self) -> List[Type]:
        """Provides all types that can be generated, including primitives."""
        generatable = list(self._generators.keys())
        generatable.extend(PRIMITIVES)
        return generatable

    def select_concrete_type(self, select_from: Optional[Type]) -> Optional[Type]:
        """Select a concrete type from the given type.
        This is required e.g. when handling union types.
        Currently only unary types, Any and Union are handled."""
        if select_from == Any:
            return randomness.choice(self.get_all_generatable_types())
        if is_union_type(select_from):
            possible_types = get_args(select_from)
            if possible_types is not None and len(possible_types) > 0:
                return randomness.choice(possible_types)
            return None
        return select_from
