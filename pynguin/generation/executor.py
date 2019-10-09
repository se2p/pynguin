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
import contextlib
import importlib
import inspect
from typing import List, Any, Tuple, Dict, Type, Callable, Union

from coverage import Coverage  # type: ignore

from pynguin.utils.exceptions import GenerationException
from pynguin.utils.proxy import MagicProxy
from pynguin.utils.statements import Sequence, Call, Assignment, Name, Attribute
from pynguin.utils.utils import get_members_from_module


def _recording_isinstance(
    obj: object, obj_type: Union[type, Tuple[Union[type, tuple], ...]]
) -> bool:
    if isinstance(obj, MagicProxy):
        # pylint: disable=protected-access
        obj._instance_check_type = obj_type  # type: ignore
    return isinstance(obj, obj_type)


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
        if self._measure_coverage:
            self._coverage = Coverage(branch=True)
            self._coverage.start()

        if not self._classes:
            self.load_modules()

        classes = self._classes
        try:
            self._reset_error_flags(sequence)
            result = self._exec(sequence, classes)
        except Exception as exception:
            # Any error we get here must have happened outside our execution
            raise GenerationException(exception)
        finally:
            if self._measure_coverage:
                self._coverage.stop()
                sequence.arcs = self._get_arcs_for_classes(classes)

                self._accumulated_coverage.get_data().update(self._coverage.get_data())
        return result

    def load_modules(self, reload: bool = False) -> None:
        """Loads the module before execution.

        :param reload: An optional boolean indicating whether modules should be
        reloaded.
        """
        if self._measure_coverage:
            self._load_coverage.start()

        modules = []
        for path in self._module_paths:
            module = importlib.import_module(path)
            modules.append(module)
            module.isinstance = _recording_isinstance  # type: ignore  # TODO(sl)

        if reload:
            for module in modules:
                # Reload all modules to also cover the import coverage
                importlib.reload(module)

        self._classes = modules.copy()
        for module in self._classes:
            members = get_members_from_module(module)
            self._classes = self._classes + [x[1] for x in members]

        if self._measure_coverage:
            self._load_coverage.stop()
            self._accumulated_coverage.get_data().update(self._load_coverage.get_data())

    def _get_arcs_for_classes(self, classes: List[Type]) -> List[Any]:
        if not self._measure_coverage:
            return []

        arcs_per_file = []
        for class_name in classes:
            if not hasattr(class_name, "__file__"):
                continue

            arcs = self._coverage.get_data().arcs(class_name.__file__)
            arcs_per_file.append(arcs)

        return arcs_per_file

    def _exec(
        self, sequence: Sequence, classes: List[Type]
    ) -> Tuple[Dict[str, Any], Dict[str, Any], List[Exception], Sequence]:
        values: Dict[str, Any] = {}
        exceptions: List[Exception] = []
        inputs: Dict[str, Any] = {}

        with open("/dev/null", mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                executed_sequence = Sequence()
                try:
                    for statement in sequence:
                        if isinstance(statement, Call):
                            func, inputs = self._exec_call(statement, values, classes)
                            executed_sequence.append(statement)
                            func()
                        elif isinstance(statement, Assignment):
                            assert isinstance(statement.rhs, Call)
                            func, inputs = self._exec_call(
                                statement.rhs, values, classes
                            )
                            executed_sequence.append(statement)
                            result = func()
                            if isinstance(statement.lhs, Name):
                                values[statement.lhs.identifier] = MagicProxy(result)
                            elif isinstance(statement.lhs, Attribute):
                                values[
                                    statement.lhs.owner.identifier
                                    + statement.lhs.attribute_name
                                ] = MagicProxy(result)
                            else:
                                raise TypeError(
                                    "Unexpected LHS type " + str(statement.lhs)
                                )
                except Exception as exception:  # pylint: disable=broad-except
                    exceptions.append(exception)
                return values, inputs, exceptions, executed_sequence

    def _exec_call(
        self, statement: Call, values: Dict[str, Any], classes: List[Type]
    ) -> Tuple[Callable, Dict[str, Any]]:
        func = statement.function
        arguments = self._get_argument_list(statement.arguments, values, classes)
        if isinstance(func, Name):
            # Call without callee, ref is the function
            ref = self._get_ref(func.identifier, values, classes)
            parameter_names = list(inspect.signature(ref).parameters)
            inputs = dict(zip(parameter_names, arguments))
            return self._get_call_wrapper(ref, arguments), inputs
        elif isinstance(func, Attribute):
            # Call with callee ref and function attributes
            if not func.owner.identifier:
                raise GenerationException("Cannot call methods on None")

            ref = self._get_ref(func.owner.identifier, values, classes)
            attribute = getattr(ref, func.attribute_name)
            parameter_names = list(inspect.signature(attribute).parameters)
            inputs = dict(zip(parameter_names, arguments))
            return self._get_call_wrapper(attribute, arguments), inputs

        raise NotImplementedError("No execution implemented for type " + str(func))

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
