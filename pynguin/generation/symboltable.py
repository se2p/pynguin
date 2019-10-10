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
"""Provides a symbol table."""
import inspect
from collections.abc import Mapping
from typing import Set, Type, Dict, Union, Callable, Any, Iterator

from pynguin.utils.exceptions import GenerationException
from pynguin.utils.statements import FunctionSignature
from pynguin.utils.string import String


class SymbolTable(Mapping):
    """Provides a symbol table."""

    _default_domain: Set[Type] = {int, String, float, complex, bool}

    def __init__(
        self,
        type_inference,  #: TypeInference,
        domains: Set[Type] = None,
        use_type_hints: bool = False,
    ) -> None:
        self._use_type_hints = use_type_hints
        self._type_inference = type_inference
        self._storage: Dict[Union[str, Callable], Any] = {}
        if domains:
            self._default_domain = domains.copy()
        else:
            self._default_domain = SymbolTable._default_domain.copy()

    def __getitem__(self, item: Union[str, Callable]) -> Any:
        return self._storage[item]

    def __setitem__(self, key: Union[str, Callable], value: Any) -> None:
        self._storage[key] = value

    def __delitem__(self, key: Union[str, Callable]) -> None:
        del self._storage[key]

    def __len__(self) -> int:
        return len(self._storage)

    def __iter__(self) -> Iterator[Union[str, Callable]]:
        return iter(self._storage)

    @staticmethod
    def get_default_domain() -> Set[Type]:
        """Returns a copy of the default domain.

        :return: A copy of the default domain
        """
        return SymbolTable._default_domain.copy()

    def add_callable(self, method: Callable) -> None:
        """Adds a callable to the symbol table.

        :param method: The callable to add
        """
        try:
            signature = inspect.signature(method)
        except (TypeError, ValueError):
            raise GenerationException(
                "Could not inspect built-in type.  Skip callable " + method.__name__
            )

        parameters = [param for _, param in signature.parameters.items()]
        primitive_domain = self._default_domain.copy()
        domains = {}
        for parameter in parameters.copy():
            if parameter.name == "self":
                parameters.remove(parameter)
            domains[parameter.name] = primitive_domain.copy()

        parameter_names = [param.name for param in parameters]

        cls = None
        names = method.__qualname__.split(".")
        if len(names) > 1:
            cls = names[0]
            method_name = names[1]
        else:
            method_name = names[0]

        module = None
        if hasattr(method_name, "__module__"):
            module = method_name.__module__

        function_signature = FunctionSignature(
            module, cls, method_name, parameter_names
        )
        self[method] = function_signature

    # pylint: disable=no-self-use
    def add_constraint(self, method: Callable, constraint) -> None:
        """Adds a constraint for a callable.

        :param method: The callable
        :param constraint: The constraint to add
        """
        raise Exception(
            "Adding constraint "
            + str(constraint)
            + " for callable "
            + str(callable)
            + " not yet implemented"
        )

    def add_constraints(self, method: Callable, constraints) -> None:
        """Add a list of constraints for a callable.

        :param method: The callable
        :param constraints: The list of constraints to add
        """
        for constraint in constraints:
            self.add_constraint(method, constraint)
