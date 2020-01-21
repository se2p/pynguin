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
"""Provides a strategy implementation that uses type hints."""
import inspect
from typing import Callable, Dict, Optional

import typing

from pynguin.typeinference.strategy import TypeInferenceStrategy, InferredMethodType


# pylint: disable=too-few-public-methods
class TypeHintsInferenceStrategy(TypeInferenceStrategy):
    """A type inference strategy that simply parses the type hints.

    For classes it inspects the `__init__` method and uses its parameters.
    """

    def infer_type_info(self, method: Callable) -> InferredMethodType:
        if inspect.isclass(method) and hasattr(method, "__init__"):
            return self._infer_type_info_for_constructor(getattr(method, "__init__"))
        return self._infer_type_info_for_method(method)

    @staticmethod
    def _infer_type_info_for_method(method: Callable) -> InferredMethodType:
        method_signature = inspect.signature(method)
        parameters: Dict[str, Optional[type]] = {}
        hints = typing.get_type_hints(method)
        for param_name in method_signature.parameters:
            parameters[param_name] = hints.get(param_name, None)

        return_type: Optional[type] = hints.get("return", None)

        return InferredMethodType(
            method_signature=method_signature,
            parameters=parameters if parameters else None,
            return_type=return_type if return_type else None,
        )

    @staticmethod
    def _infer_type_info_for_constructor(method: Callable) -> InferredMethodType:
        method_signature = inspect.signature(method)
        parameters: Dict[str, Optional[type]] = {}
        hints = typing.get_type_hints(method)
        for param_name in method_signature.parameters:
            if param_name == "self":
                continue
            parameters[param_name] = hints.get(param_name, None)

        return InferredMethodType(
            method_signature=method_signature,
            parameters=parameters if parameters else None,
            return_type=None,
        )
