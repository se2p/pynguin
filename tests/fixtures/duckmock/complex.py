#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# noqa
import dataclasses
import logging

from pynguin.setup.testcluster import TestCluster
from pynguin.typeinference.strategy import TypeInferenceStrategy
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
)


@dataclasses.dataclass(eq=True, frozen=True)
class DependencyPair:
    """
    Represents a dependency for a type that still needs to be resolved.
    We also store the recursion level, so we can enforce a limit on it.
    The recursion level is excluded from hash/eq so we don't get duplicate
    dependencies at different recursion levels.
    """

    dependency_type: type = dataclasses.field(compare=True, hash=True)
    recursion_level: int = dataclasses.field(compare=False, hash=False)


class TestClusterGenerator:
    """Generate a new test cluster"""

    _logger = logging.getLogger(__name__)

    def __init__(self, modules_name: str):
        pass

    @staticmethod
    def _initialise_type_inference_strategies() -> list[TypeInferenceStrategy]:
        pass

    def generate_cluster(self) -> TestCluster:
        """Generate new test cluster from the configured modules.

        Returns:
            The new test cluster
        """

    def _add_callable_dependencies(
        self, call: GenericCallableAccessibleObject, recursion_level: int
    ) -> None:
        """Add required dependencies.

        Args:
            call: The object whose parameter types should be added as dependencies.
            recursion_level: The current level of recursion of the search
        """

    def _add_dependency(self, klass: type, recursion_level: int, add_to_test: bool):
        """Add constructor/methods/attributes of the given type to the test cluster.

        Args:
            klass: The type of the dependency
            recursion_level: the current recursion level of the search
            add_to_test: whether the accessible objects are also added to objects
                under test.
        """

    @staticmethod
    def _is_constructor(method_name: str) -> bool:
        pass

    @staticmethod
    def _is_method_defined_in_class(class_: type, method: object) -> bool:
        pass

    @staticmethod
    def _is_protected(method_name: str) -> bool:
        pass

    @staticmethod
    def _discard_accessible_with_missing_type_hints(
        accessible_object: GenericCallableAccessibleObject,
    ) -> bool:
        """Should we discard accessible objects that are not fully type hinted?

        Args:
            accessible_object: the object to check

        Returns:
            Whether or not the accessible should be discarded
        """

    def _resolve_dependencies_recursive(self):
        """Resolve the currently open dependencies."""
