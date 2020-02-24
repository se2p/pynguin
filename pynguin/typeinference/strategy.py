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
"""Provides an inference strategy for types."""
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, field
from inspect import Signature
from typing import Callable, Dict, Optional


@dataclass
class InferredSignature:
    """Encapsulates the types inferred for a method"""

    signature: Signature
    parameters: Dict[str, Optional[type]] = field(default_factory=dict)
    return_type: Optional[type] = None

    def update_parameter_type(
        self, parameter_name: str, parameter_type: Optional[type]
    ) -> None:
        """Updates the type of one parameter.

        :param parameter_name: The name of the parameter
        :param parameter_type: The new type of the parameter
        """
        assert parameter_name in self.parameters
        self.parameters[parameter_name] = parameter_type

    def update_return_type(self, return_type: Optional[type]) -> None:
        """Updates the return type

        :param return_type: The new return type
        """
        self.return_type = return_type


# pylint: disable=too-few-public-methods
class TypeInferenceStrategy(metaclass=ABCMeta):
    """Provides an abstract base class for inference strategies for types."""

    @abstractmethod
    def infer_type_info(self, method: Callable) -> InferredSignature:
        """Infers the type information for a callable.

        :param method: The callable we try to infer type information for
        :return: A MethodType object with the inference results
        """
