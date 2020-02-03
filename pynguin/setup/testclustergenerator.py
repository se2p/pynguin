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
"""Provides capabilites to create a test cluster"""
import importlib
import inspect
import logging

from typing import List
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


class TestClusterGenerator:  # pylint: disable=too-few-public-methods
    """Generate a new test cluster"""

    primitives = {int, str, bool, float, complex}

    _logger = logging.getLogger(__name__)

    def __init__(self, modules_names: List[str]):
        self._module_names = modules_names
        self._test_cluster: TestCluster = TestCluster()

    def generate_cluster(self) -> TestCluster:
        """Generate new test cluster from the configured modules."""
        # TODO(fk) use configured inference strategy
        inference = typeinference.TypeInference(
            strategies=[TypeHintsInferenceStrategy()]
        )

        self._logger.debug("Generating test cluster")
        for module in self._module_names:
            self._logger.debug("Analyzing module %s", module)
            imported = importlib.import_module(module)
            for class_name, klass in inspect.getmembers(imported, inspect.isclass):
                self._logger.debug("Analyzing class %s", class_name)
                # TODO(fk) handle multiple strategies?
                generic_constructor = GenericConstructor(
                    klass, inference.infer_type_info(klass.__init__)[0]
                )
                self._test_cluster.add_generator(generic_constructor)
                self._test_cluster.add_accessible_object_under_test(generic_constructor)
                self._add_callable_dependencies(generic_constructor, 1)

                for method_name, method in inspect.getmembers(
                    klass, inspect.isfunction
                ):
                    # TODO(fk) why does inspect.ismethod not work here?!
                    self._logger.debug(
                        "Analyzing method %s.%s", class_name, method_name
                    )
                    if method_name == "__init__":
                        # The constructor is handled elsewhere.
                        continue
                    generic_method = GenericMethod(
                        klass, method, inference.infer_type_info(method)[0]
                    )
                    self._test_cluster.add_generator(generic_method)
                    self._test_cluster.add_accessible_object_under_test(generic_method)
                    self._add_callable_dependencies(generic_method, 1)
                # TODO(fk) how do we find attributes?
            for function_name, funktion in inspect.getmembers(
                imported, inspect.isfunction
            ):
                self._logger.debug("Analyzing function %s", function_name)
                generic_function = GenericFunction(
                    funktion, inference.infer_type_info(funktion)[0]
                )
                self._test_cluster.add_generator(generic_function)
                self._test_cluster.add_accessible_object_under_test(generic_function)
                self._add_callable_dependencies(generic_function, 1)
        return self._test_cluster

    def _add_callable_dependencies(
        self, call: GenericCallableAccessibleObject, recursion_level: int
    ) -> None:
        """Add required dependencies."""
        self._logger.debug("Find dependencies for %s", call)
        if recursion_level > config.INSTANCE.max_cluster_recursion:
            return
        # TODO(fk) Implement me

    def _add_dependency(self):
        """Add further dependencies."""
        # TODO(fk) Implement me
