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
"""Provides an executor that executes generated sequences."""
import inspect
from typing import List, Any, Tuple, Dict, Type, Callable

from coverage import Coverage  # type: ignore

from pynguin.utils.proxy import MagicProxy
from pynguin.utils.statements import Sequence, Call, Assignment, Name


# pylint: disable=no-else-return, inconsistent-return-statements,protected-access
class Executor:
    """An executor that executes the generated sequences."""

    def __init__(self, module_paths: List[str], measure_coverage: bool = False) -> None:
        self._module_paths = module_paths
        self._measure_coverage = measure_coverage
        self._coverage: Coverage = None
        self._accumulated_coverage: Coverage = Coverage(branch=True)
        self._load_coverage: Coverage = Coverage(branch=True)
        self._classes: List[Any] = []
        self.load_modules()

    @property
    def accumulated_coverage(self) -> Coverage:
        """Provides access to the accumulated coverage property."""
        return self._accumulated_coverage

    def execute(
        self, sequence: Sequence
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Exception], Sequence]:
        """Executes a sequence of statements.

        :param sequence:
        :return:
        """

    def load_modules(self, reload: bool = False) -> None:
        """Loads the module before execution.

        :param reload: An optional boolean indicating whether modules should be
        reloaded.
        """

    def _get_arcs_for_classes(self, classes: List[Type]) -> List[Any]:
        pass

    def _exec(
        self, sequence: Sequence, classes: List[Type]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Exception], Sequence]:
        pass

    def _exec_call(
        self, statement: Call, values: Dict[str, Any], classes: List[Type]
    ) -> Tuple[Callable, Dict[str, Any]]:
        pass

    def _get_argument_list(
        self,
        statement_arguments: List[Any],
        values: Dict[str, Any],
        classes: List[Type],
    ) -> List[Any]:
        arguments: List[Any] = []

        for argument in statement_arguments:
            if (
                isinstance(argument, MagicProxy)
                and isinstance(argument._obj, Name)  # type: ignore
                or isinstance(argument, Name)
            ):
                # There is no need to wrap refs in magic proxies, since this is done
                # when they are added to the value list
                ref = self._get_ref(
                    argument.identifier,  # type: ignore
                    values,
                    classes,
                )
                arguments.append(ref)
            else:
                arguments.append(argument)

        return arguments

    @staticmethod
    def _get_ref(name: str, values: Dict[str, Any], classes: List[Type]) -> Any:
        for label, ref in values.items():
            if label == name:
                return ref

        for class_type in classes:
            if class_type.__name__ == name:
                return class_type

            if class_type.__name__ in name:
                identifier = name.replace(class_type.__name__ + ".", "")
                for key, value in inspect.getmembers(class_type):
                    if key == identifier:
                        return value

    @staticmethod
    def _get_call_wrapper(func: Any, arguments: List[Any]) -> Any:
        def wrapper():
            if arguments:
                return func(*arguments)
            return func()

        return wrapper

    @staticmethod
    def _reset_error_flags(sequence: Sequence) -> None:
        def reset(var: Any) -> Any:
            if hasattr(var, "_hasError"):
                var._hasError = False
            return var

        for statement in sequence:
            if isinstance(statement, Call):
                statement.arguments = list(map(reset, statement.arguments))
            elif isinstance(statement, Assignment) and isinstance(statement.rhs, Call):
                statement.rhs.arguments = list(map(reset, statement.rhs.arguments))
