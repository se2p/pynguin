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
from typing import List, Set, Type

from typing_inspect import get_args, is_union_type

import pynguin.configuration as config
from pynguin.setup.testcluster import TestCluster
from pynguin.typeinference import typeinference
from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy
from pynguin.typeinference.strategy import TypeInferenceStrategy
from pynguin.typeinference.stubstrategy import StubInferenceStrategy
from pynguin.typeinference.typehintsstrategy import TypeHintsInferenceStrategy
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.type_utils import (
    class_in_module,
    function_in_module,
    get_class_that_defined_method,
    is_primitive_type,
    should_skip_parameter,
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

    def __init__(self, modules_name: str):
        self._module_name = modules_name
        self._analyzed_classes: Set[Type] = set()
        self._dependencies_to_solve: Set[DependencyPair] = set()
        self._test_cluster: TestCluster = TestCluster()
        self._inference = typeinference.TypeInference(
            strategies=self._initialise_type_inference_strategies()
        )

    @staticmethod
    def _initialise_type_inference_strategies() -> List[TypeInferenceStrategy]:
        strategy = config.INSTANCE.type_inference_strategy
        if strategy == config.TypeInferenceStrategy.NONE:
            return [NoTypeInferenceStrategy()]
        if strategy == config.TypeInferenceStrategy.STUB_FILES:
            if config.INSTANCE.stub_dir is None:
                raise ConfigurationException(
                    "Missing configuration value `stub_dir' for StubInferenceStrategy"
                )
            return [StubInferenceStrategy(config.INSTANCE.stub_dir)]
        if strategy == config.TypeInferenceStrategy.TYPE_HINTS:
            return [TypeHintsInferenceStrategy()]
        raise ConfigurationException("Invalid type-inference strategy")

    def generate_cluster(self) -> TestCluster:
        """Generate new test cluster from the configured modules.

        Returns:
            The new test cluster
        """
        self._logger.debug("Generating test cluster")
        self._logger.debug("Analyzing module %s", self._module_name)
        module = importlib.import_module(self._module_name)
        for _, klass in inspect.getmembers(module, class_in_module(self._module_name)):
            self._add_dependency(klass, 1, True)

        for function_name, funktion in inspect.getmembers(
            module, function_in_module(self._module_name)
        ):

            generic_function = GenericFunction(
                funktion, self._inference.infer_type_info(funktion)[0]
            )
            if self._is_protected(
                function_name
            ) or self._discard_accessible_with_missing_type_hints(generic_function):
                self._logger.debug("Skip function %s", function_name)
                continue

            self._logger.debug("Analyzing function %s", function_name)
            self._test_cluster.add_generator(generic_function)
            self._test_cluster.add_accessible_object_under_test(generic_function)
            self._add_callable_dependencies(generic_function, 1)
        self._resolve_dependencies_recursive()
        return self._test_cluster

    def _add_callable_dependencies(
        self, call: GenericCallableAccessibleObject, recursion_level: int
    ) -> None:
        """Add required dependencies.

        Args:
            call: The object whose parameter types should be added as dependencies.
            recursion_level: The current level of recursion of the search
        """
        self._logger.debug("Find dependencies for %s", call)
        if recursion_level > config.INSTANCE.max_cluster_recursion:
            self._logger.debug("Reached recursion limit. No more dependencies added.")
            return
        for param_name, type_ in call.inferred_signature.parameters.items():
            self._logger.debug("Resolving '%s' (%s)", param_name, type_)
            types = {type_}
            if is_union_type(type_):
                types = set(get_args(type_))

            for elem in types:
                if is_primitive_type(elem):
                    self._logger.debug("Not following primitive argument.")
                    continue
                if inspect.isclass(elem):
                    assert elem
                    self._logger.debug("Adding dependency for class %s", elem)
                    self._dependencies_to_solve.add(
                        DependencyPair(elem, recursion_level)
                    )
                else:
                    self._logger.debug("Found typing annotation %s, skipping", elem)
                    # TODO(fk) fully support typing annotations.

    def _add_dependency(self, klass: Type, recursion_level: int, add_to_test: bool):
        """Add constructor/methods/attributes of the given type to the test cluster.

        Args:
            klass: The type of the dependency
            recursion_level: the current recursion level of the search
            add_to_test: whether the accessible objects are also added to objects
                under test.
        """
        assert inspect.isclass(klass), "Can only add dependencies for classes."
        if klass in self._analyzed_classes:
            self._logger.debug("Class %s already analyzed", klass)
            return
        self._analyzed_classes.add(klass)
        self._logger.debug("Analyzing class %s", klass)
        generic_constructor = GenericConstructor(
            klass, self._inference.infer_type_info(klass.__init__)[0]
        )
        if self._discard_accessible_with_missing_type_hints(generic_constructor):
            return

        self._test_cluster.add_generator(generic_constructor)
        if add_to_test:
            self._test_cluster.add_accessible_object_under_test(generic_constructor)
        self._add_callable_dependencies(generic_constructor, recursion_level)

        for method_name, method in inspect.getmembers(klass, inspect.isfunction):
            # TODO(fk) why does inspect.ismethod not work here?!
            self._logger.debug("Analyzing method %s", method_name)

            generic_method = GenericMethod(
                klass, method, self._inference.infer_type_info(method)[0]
            )

            if (
                self._is_constructor(method_name)
                or not self._is_method_defined_in_class(klass, method)
                or self._is_protected(method_name)
                or self._discard_accessible_with_missing_type_hints(generic_method)
            ):
                # Skip methods that should not be added to the cluster here.
                # Constructors are handled elsewhere; inherited methods should not be
                # part of the cluster, only overridden methods; private methods should
                # neither be part of the cluster.
                continue

            self._test_cluster.add_generator(generic_method)
            self._test_cluster.add_modifier(klass, generic_method)
            if add_to_test:
                self._test_cluster.add_accessible_object_under_test(generic_method)
            self._add_callable_dependencies(generic_method, recursion_level)
        # TODO(fk) how do we find attributes?

    @staticmethod
    def _is_constructor(method_name: str) -> bool:
        return method_name == "__init__"

    @staticmethod
    def _is_method_defined_in_class(class_: type, method: object) -> bool:
        return class_ == get_class_that_defined_method(method)

    @staticmethod
    def _is_protected(method_name: str) -> bool:
        return method_name.startswith("_") and not method_name.startswith("__")

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
        if config.INSTANCE.guess_unknown_types:
            return False
        inf_sig = accessible_object.inferred_signature
        return any(
            [
                not should_skip_parameter(inf_sig, param) and type_ is None
                for param, type_ in inf_sig.parameters.items()
            ]
        )

    def _resolve_dependencies_recursive(self):
        """Resolve the currently open dependencies."""
        while self._dependencies_to_solve:
            to_solve = self._dependencies_to_solve.pop()
            self._add_dependency(
                to_solve.dependency_type, to_solve.recursion_level + 1, False
            )
