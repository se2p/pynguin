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
"""Provides capabilities to create a test cluster"""
import dataclasses
import importlib
import inspect
import logging

from typing import List, Type, Set
from pynguin.typeinference import typeinference
from pynguin.typeinference.typehintsstrategy import TypeHintsInferenceStrategy
import pynguin.configuration as config
from pynguin.setup.testcluster import TestCluster
from pynguin.utils.generic.genericaccessibleobject import (
    GenericMethod,
    GenericFunction,
    GenericConstructor,
    GenericCallableAccessibleObject,
)
from pynguin.utils.type_utils import (
    is_primitive_type,
    class_in_module,
    function_in_module,
)


@dataclasses.dataclass(eq=True, frozen=True)
class DependencyPair:
    """
    Represents a dependency for a type that still needs to be resolved.
    We also store the recursion level, so we can enforce a limit on it.
    The recursion level is excluded from hash/eq so we don't get duplicate
    dependencies at different recursion levels.
    """

    dependency_type: Type = dataclasses.field(compare=True, hash=True)
    recursion_level: int = dataclasses.field(compare=False, hash=False)


class TestClusterGenerator:  # pylint: disable=too-few-public-methods
    """Generate a new test cluster"""

    _logger = logging.getLogger(__name__)

    def __init__(self, modules_names: List[str]):
        self._module_names = modules_names
        self._analyzed_classes: Set[Type] = set()
        self._dependencies_to_solve: Set[DependencyPair] = set()
        self._test_cluster: TestCluster = TestCluster()
        # TODO(fk) use configured inference strategy
        self._inference = typeinference.TypeInference(
            strategies=[TypeHintsInferenceStrategy()]
        )

    def generate_cluster(self) -> TestCluster:
        """Generate new test cluster from the configured modules."""
        self._logger.debug("Generating test cluster")
        for module_name in self._module_names:
            self._logger.debug("Analyzing module %s", module_name)
            module = importlib.import_module(module_name)
            for _, klass in inspect.getmembers(module, class_in_module(module_name)):
                self._add_dependency(klass, 1, True)

            for function_name, funktion in inspect.getmembers(
                module, function_in_module(module_name)
            ):
                self._logger.debug("Analyzing function %s", function_name)
                generic_function = GenericFunction(
                    funktion, self._inference.infer_type_info(funktion)[0]
                )
                self._test_cluster.add_generator(generic_function)
                self._test_cluster.add_accessible_object_under_test(generic_function)
                self._add_callable_dependencies(generic_function, 1)
        self._resolve_dependencies_recursive()
        return self._test_cluster

    def _add_callable_dependencies(
        self, call: GenericCallableAccessibleObject, recursion_level: int
    ) -> None:
        """
        Add required dependencies.
        :param call The object whose parameter types should be added as dependencies.
        """
        self._logger.debug("Find dependencies for %s", call)
        if recursion_level > config.INSTANCE.max_cluster_recursion:
            self._logger.debug("Reached recursion limit. No more dependencies added.")
            return
        for param_name, type_ in call.inferred_signature.parameters.items():
            self._logger.debug("Resolving '%s' (%s)", param_name, type_)
            if is_primitive_type(type_):
                self._logger.debug("Not following primitive argument.")
                continue
            if inspect.isclass(type_):
                assert type_
                if type_ in self._analyzed_classes:
                    continue
                self._logger.debug("Adding dependency for class %s", type_)
                self._dependencies_to_solve.add(DependencyPair(type_, recursion_level))
            else:
                self._logger.debug("Found typing annotation %s, skipping", type_)
                # TODO(fk) fully support typing annotations.

    def _add_dependency(self, klass: Type, recursion_level: int, add_to_test: bool):
        """
        Add constructor/methods/attributes of the given type to the test cluster.
        :param add_to_test if true, the accessible objects are also added to objects under test.
        """
        assert inspect.isclass(klass), "Can only add dependencies for classes."
        if klass in self._analyzed_classes:
            self._logger.debug("Class %s already analyzed", klass)
            return
        self._analyzed_classes.add(klass)
        self._logger.debug("Analyzing class %s", klass)
        # TODO(fk) handle multiple strategies?
        generic_constructor = GenericConstructor(
            klass, self._inference.infer_type_info(klass.__init__)[0]
        )
        self._test_cluster.add_generator(generic_constructor)
        if add_to_test:
            self._test_cluster.add_accessible_object_under_test(generic_constructor)
        self._add_callable_dependencies(generic_constructor, recursion_level)

        for method_name, method in inspect.getmembers(klass, inspect.isfunction):
            # TODO(fk) why does inspect.ismethod not work here?!
            self._logger.debug("Analyzing method %s", method_name)
            if method_name == "__init__":
                # The constructor is handled elsewhere.
                continue
            generic_method = GenericMethod(
                klass, method, self._inference.infer_type_info(method)[0]
            )
            self._test_cluster.add_generator(generic_method)
            if add_to_test:
                self._test_cluster.add_accessible_object_under_test(generic_method)
            self._add_callable_dependencies(generic_method, recursion_level)
        # TODO(fk) how do we find attributes?

    def _resolve_dependencies_recursive(self):
        """Resolve the currently open dependencies."""
        while self._dependencies_to_solve:
            to_solve = self._dependencies_to_solve.pop()
            self._add_dependency(
                to_solve.dependency_type, to_solve.recursion_level + 1, False
            )
