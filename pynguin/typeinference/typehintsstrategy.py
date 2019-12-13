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

    def _infer_type_info_for_method(self, method: Callable) -> InferredMethodType:
        method_signature = inspect.signature(method)
        parameters: Dict[str, Optional[type]] = {}
        for param_name, param_type in method_signature.parameters.items():
            parameters[param_name] = self._extract_parameter_type(param_type)

        return_types: Optional[type] = None
        if method_signature.return_annotation is not None and (
            method_signature.return_annotation
            not in [inspect.Parameter.empty, inspect.Signature.empty]
        ):
            return_types = method_signature.return_annotation

        return InferredMethodType(
            method_signature=method_signature,
            parameters=parameters if parameters else None,
            return_type=return_types if return_types else None,
        )

    def _infer_type_info_for_constructor(self, method: Callable) -> InferredMethodType:
        method_signature = inspect.signature(method)
        parameters: Dict[str, Optional[type]] = {}
        for param_name, param_type in method_signature.parameters.items():
            if param_name == "self":
                continue
            parameters[param_name] = self._extract_parameter_type(param_type)

        return InferredMethodType(
            method_signature=method_signature,
            parameters=parameters if parameters else None,
            return_type=None,
        )

    @staticmethod
    def _extract_parameter_type(param_type) -> Optional[type]:
        if param_type.annotation is None or (
            param_type.annotation in [inspect.Parameter.empty, inspect.Signature.empty]
        ):
            return None
        return param_type.annotation
