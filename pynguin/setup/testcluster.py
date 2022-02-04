#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a test cluster."""
from __future__ import annotations

import json
import logging
import typing
from abc import ABC, abstractmethod
from typing import Any

from ordered_set import OrderedSet
from typing_inspect import get_args, is_union_type

from pynguin.instrumentation.instrumentation import CODE_OBJECT_ID_KEY
from pynguin.utils import randomness, type_utils
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)
from pynguin.utils.type_utils import COLLECTIONS, PRIMITIVES

if typing.TYPE_CHECKING:  # Break circular dependencies at runtime.
    import pynguin.ga.computations as ff
    import pynguin.generation.algorithms.archive as arch
    from pynguin.testcase.execution import KnownData
    from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class TestCluster(ABC):
    """A test cluster which contains all methods/constructors/functions
    and all required transitive dependencies.
    """

    @property
    @abstractmethod
    def accessible_objects_under_test(self) -> OrderedSet[GenericAccessibleObject]:
        """Provides all accessible objects that are under test.

        Returns:
            The set of all accessible objects under test
        """

    @abstractmethod
    def num_accessible_objects_under_test(self) -> int:
        """Provide the number of accessible objects under test.

        This is useful to check if there even is something to test.

        Returns:
            The number of all accessibles under test
        """

    @abstractmethod
    def get_generators_for(self, for_type: type) -> OrderedSet[GenericAccessibleObject]:
        """Retrieve all known generators for the given type.

        Args:
            for_type: The type we want to have the generators for

        Returns:
            The set of all generators for that type
        """

    @abstractmethod
    def get_modifiers_for(self, for_type: type) -> OrderedSet[GenericAccessibleObject]:
        """Get all known modifiers of a type.

        This currently does not take inheritance into account.

        Args:
            for_type: The type

        Returns:
            The set of all accessibles that can modify the type
        """

    @property
    @abstractmethod
    def generators(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        """Provides all available generators.

        Returns:
            A dictionary of types and their generating accessibles
        """

    @property
    @abstractmethod
    def modifiers(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        """Provides all available modifiers.

        Returns:
            A dictionary of types and their modifying accessibles
        """

    @abstractmethod
    def get_random_accessible(self) -> GenericAccessibleObject | None:
        """Provide a random accessible of the unit under test.

        Returns:
            A random accessible
        """

    @abstractmethod
    def get_random_call_for(self, type_: type) -> GenericAccessibleObject:
        """Get a random modifier for the given type.

        Args:
            type_: The type

        Returns:
            A random modifier for that type

        Raises:
            ConstructionFailedException: if no modifiers for the type exist
        """

    @abstractmethod
    def get_all_generatable_types(self) -> list[type]:
        """Provides all types that can be generated, including primitives
        and collections.

        Returns:
            A list of all types that can be generated
        """

    @abstractmethod
    def select_concrete_type(self, select_from: type | None) -> type | None:
        """Select a concrete type from the given type.

        This is required e.g. when handling union types.
        Currently only unary types, Any and Union are handled.

        Args:
            select_from: An optional type

        Returns:
            An optional type
        """


class FullTestCluster(TestCluster):
    """A test cluster which contains all methods/constructors/functions
    and all required transitive dependencies.
    """

    def __init__(self):
        """Create new test cluster."""
        self._generators: dict[type, OrderedSet[GenericAccessibleObject]] = {}
        self._modifiers: dict[type, OrderedSet[GenericAccessibleObject]] = {}
        self._accessible_objects_under_test: OrderedSet[
            GenericAccessibleObject
        ] = OrderedSet()

    def add_generator(self, generator: GenericAccessibleObject) -> None:
        """Add the given accessible as a generator.

        It is only added if the type is known, not primitive and not NoneType.

        Args:
            generator: The accessible object
        """
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
            self._generators[type_] = OrderedSet([generator])

    def add_accessible_object_under_test(self, obj: GenericAccessibleObject) -> None:
        """Add accessible object to the objects under test.

        Args:
            obj: The accessible object
        """
        self._accessible_objects_under_test.add(obj)

    def add_modifier(self, type_: type, obj: GenericAccessibleObject) -> None:
        """Add a modifier.

        A modified is something that can be used to modify the given type,
        e.g. a method.

        Args:
            type_: The type that can be modified
            obj: The accessible that can modify
        """
        if type_ in self._modifiers:
            self._modifiers[type_].add(obj)
        else:
            self._modifiers[type_] = OrderedSet([obj])

    @property
    def accessible_objects_under_test(self) -> OrderedSet[GenericAccessibleObject]:
        return self._accessible_objects_under_test

    def num_accessible_objects_under_test(self) -> int:
        return len(self._accessible_objects_under_test)

    def get_generators_for(self, for_type: type) -> OrderedSet[GenericAccessibleObject]:
        if for_type in self._generators:
            return self._generators[for_type]
        return OrderedSet()

    def get_modifiers_for(self, for_type: type) -> OrderedSet[GenericAccessibleObject]:
        if for_type in self._modifiers:
            return self._modifiers[for_type]
        return OrderedSet()

    @property
    def generators(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        return self._generators

    @property
    def modifiers(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        return self._modifiers

    def get_random_accessible(self) -> GenericAccessibleObject | None:
        if self.num_accessible_objects_under_test() == 0:
            return None
        return randomness.choice(self._accessible_objects_under_test)

    def get_random_call_for(self, type_: type) -> GenericAccessibleObject:
        accessible_objects = self.get_modifiers_for(type_)
        if len(accessible_objects) == 0:
            raise ConstructionFailedException("No modifiers for " + str(type_))
        return randomness.choice(accessible_objects)

    def get_all_generatable_types(self) -> list[type]:
        generatable = list(self._generators.keys())
        generatable.extend(PRIMITIVES)
        generatable.extend(COLLECTIONS)
        return generatable

    def select_concrete_type(self, select_from: type | None) -> type | None:
        if select_from == Any:  # pylint:disable=comparison-with-callable
            return randomness.choice(self.get_all_generatable_types())
        if is_union_type(select_from):
            possible_types = get_args(select_from)
            if possible_types is not None and len(possible_types) > 0:
                return randomness.choice(possible_types)
            return None
        return select_from


class FilteredTestCluster(TestCluster):
    """A test cluster that wraps another test cluster.
    This test cluster forwards most methods to the wrapped delegate.

    This test cluster filters out accessible objects under test that are already
    fully covered, in order to focus the search on areas that are not yet fully covered.
    """

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        test_cluster: TestCluster,
        archive: arch.Archive,
        known_data: KnownData,
        targets: OrderedSet[ff.TestCaseFitnessFunction],
    ):
        self._delegate = test_cluster
        self._known_data = known_data
        self._code_object_id_to_accessible_object: dict[
            int, GenericCallableAccessibleObject
        ] = {
            json.loads(acc.callable.__code__.co_consts[0])[CODE_OBJECT_ID_KEY]: acc
            for acc in test_cluster.accessible_objects_under_test
            if isinstance(acc, GenericCallableAccessibleObject)
            and hasattr(acc.callable, "__code__")
        }
        # Checking for __code__ is necessary, because the __init__ of a class that does
        # not define __init__ points to some internal CPython stuff.

        self._accessible_to_targets: dict[
            GenericCallableAccessibleObject, OrderedSet
        ] = {
            acc: OrderedSet()
            for acc in self._code_object_id_to_accessible_object.values()
        }
        for target in targets:
            if (acc := self._get_accessible_object_for_target(target)) is not None:
                targets_for_acc = self._accessible_to_targets[acc]
                targets_for_acc.add(target)

        # Get informed by archive, when a target is covered.
        archive.add_on_target_covered(self._on_target_covered)

    def _get_accessible_object_for_target(
        self, target: ff.TestCaseFitnessFunction
    ) -> GenericCallableAccessibleObject | None:
        code_object_id: int | None = target.code_object_id
        while code_object_id is not None:
            if (
                acc := self._code_object_id_to_accessible_object.get(
                    code_object_id, None
                )
            ) is not None:
                return acc
            code_object_id = self._known_data.existing_code_objects[
                code_object_id
            ].parent_code_object_id
        return None

    def _on_target_covered(self, target: ff.TestCaseFitnessFunction) -> None:
        acc = self._get_accessible_object_for_target(target)
        if acc is not None:
            targets_for_acc = self._accessible_to_targets.get(acc)
            assert targets_for_acc is not None
            targets_for_acc.remove(target)
            if len(targets_for_acc) == 0:
                self._accessible_to_targets.pop(acc)
                self._logger.debug(
                    "Removed %s from test cluster because all "
                    "targets within it are covered",
                    acc,
                )

    @property
    def accessible_objects_under_test(self) -> OrderedSet[GenericAccessibleObject]:
        accessibles = self._accessible_to_targets.keys()
        if len(accessibles) == 0:
            # Should never happen, just in case everything is already covered?
            return self._delegate.accessible_objects_under_test
        return OrderedSet(accessibles)

    def num_accessible_objects_under_test(self) -> int:
        return self._delegate.num_accessible_objects_under_test()

    def get_generators_for(self, for_type: type) -> OrderedSet[GenericAccessibleObject]:
        return self._delegate.get_generators_for(for_type)

    def get_modifiers_for(self, for_type: type) -> OrderedSet[GenericAccessibleObject]:
        return self._delegate.get_modifiers_for(for_type)

    @property
    def generators(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        return self._delegate.generators

    @property
    def modifiers(self) -> dict[type, OrderedSet[GenericAccessibleObject]]:
        return self._delegate.modifiers

    def get_random_accessible(self) -> GenericAccessibleObject | None:
        accessibles = self._accessible_to_targets.keys()
        if len(accessibles) == 0:
            return self._delegate.get_random_accessible()
        return randomness.choice(OrderedSet(accessibles))

    def get_random_call_for(self, type_: type) -> GenericAccessibleObject:
        return self._delegate.get_random_call_for(type_)

    def get_all_generatable_types(self) -> list[type]:
        return self._delegate.get_all_generatable_types()

    def select_concrete_type(self, select_from: type | None) -> type | None:
        return self._delegate.select_concrete_type(select_from)
