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
from typing import Type, Set, Dict, cast

from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class TestCluster:
    """A test cluster which contains all methods/constructors/functions
    and all required transitive dependencies.
    """

    def __init__(self):
        """Create new test cluster."""
        self._generators: Dict[Type, Set[GenericAccessibleObject]] = cast(
            Dict[Type, Set[GenericAccessibleObject]], dict()
        )
        self._accessible_objects_under_test: Set[GenericAccessibleObject] = set()

    def add_generator(self, generator: GenericAccessibleObject) -> None:
        """Add the given accessible as a generator, if the type is known and not NoneType."""
        type_ = generator.generated_type()
        if type_ is None or type_utils.is_none_type(type_):
            return
        if type_ in self._generators:
            self._generators[type_].add(generator)
        else:
            self._generators[type_] = {generator}

    def add_accessible_object_under_test(self, obj: GenericAccessibleObject):
        """Add accessible object to the objects under test."""
        self._accessible_objects_under_test.add(obj)

    @property
    def accessible_objects_under_test(self) -> Set[GenericAccessibleObject]:
        """Provides all accessible objects that are under test."""
        return self._accessible_objects_under_test

    def get_generators_for(self, for_type: Type) -> Set[GenericAccessibleObject]:
        """
        Retrieve all known generators for the given type which are
        known within the test cluster.
        """
        if for_type in self._generators:
            return self._generators[for_type]
        return set()

    @property
    def generators(self) -> Dict[Type, Set[GenericAccessibleObject]]:
        """Provides all generators available."""
        return self._generators
