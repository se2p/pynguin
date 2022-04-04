#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides analyses for a module's type information."""
from __future__ import annotations

import enum
import inspect
from dataclasses import dataclass, field
from inspect import Parameter, Signature, signature
from typing import Any, Callable, get_type_hints

from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.type_utils import wrap_var_param_type


@dataclass
class InferredSignature:
    """Encapsulates the types inferred for a method.

    The fields contain the following:

    * ``signature``: Holds an :py:class:`inspect.Signature` object as generated from
      the :py:func:`inspect.signature` function.
    * ``parameters``: A dictionary mapping a parameter name to its type, if any.
    * ``return_type``: The return type of a method, if any.

    The semantics of the ``parameters`` and ``return_type`` value for ``None`` is given
    as follows: the value ``None`` means that we do not yet know anything about this
    type; the value ``NoneType`` means that this parameter or return type is of type
    ``None``,  i.e., there is no parameter or return value.

    Consider the following example:

    * ``def foo()`` with ``return_type = None`` means we do not know what the return
      type is
    * ``def bar() -> None`` with ``return_type = type(None) = NoneType`` means that the
      function odes not return anything.

    The types shall not be updated directly!  One is supposed to use the methods
    :py:meth:`update_parameter_type` and :py:meth:`update_return_type` to update the
    parameter or return type, respectively.  These methods will also adjust the value of
    the ``signature`` field by generating a new :py:class:`inspect.Signature` instance
    accordingly.
    """

    signature: Signature
    parameters: dict[str, type | None] = field(default_factory=dict)
    return_type: type | None = Any  # type: ignore

    def update_parameter_type(
        self, parameter_name: str, parameter_type: type | None
    ) -> None:
        """Updates the type of one parameter.

        Args:
            parameter_name: The name of the parameter
            parameter_type: The new type of the parameter
        """
        assert parameter_name in self.parameters
        self.parameters[parameter_name] = parameter_type
        self.__update_signature_parameter(parameter_name, parameter_type)

    def update_return_type(self, return_type: type | None) -> None:
        """Update the return type.

        Args:
            return_type: The new return type
        """
        self.return_type = return_type
        self.__update_signature_return_type(return_type)

    def __update_signature_parameter(
        self, parameter_name: str, parameter_type: type | None
    ) -> None:
        current_parameter: Parameter | None = self.signature.parameters.get(
            parameter_name
        )
        assert current_parameter is not None, "Cannot happen due to previous check"
        new_parameter = current_parameter.replace(annotation=parameter_type)
        new_parameters = [
            new_parameter if key == parameter_name else value
            for key, value in self.signature.parameters.items()
        ]
        new_signature = self.signature.replace(parameters=new_parameters)
        self.signature = new_signature

    def __update_signature_return_type(self, return_type: type | None) -> None:
        new_signature = self.signature.replace(return_annotation=return_type)
        self.signature = new_signature


class TypeInferenceStrategy(enum.Enum):
    """The type-inference strategy."""

    NONE = enum.auto()
    TYPE_HINTS = enum.auto()


def infer_type_info(
    method: Callable,
    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS,
) -> InferredSignature:
    """Infers the type information for a callable.

    Args:
        method: The callable we try to infer type information for
        type_inference_strategy: Whether to incorporate type annotations

    Returns:
        The inference result

    Raises:
        ConfigurationException: in case an unknown type-inference strategy was selected
    """
    match type_inference_strategy:
        case TypeInferenceStrategy.TYPE_HINTS:
            return infer_type_info_with_types(method)
        case TypeInferenceStrategy.NONE:
            return infer_type_info_no_types(method)
        case _:
            raise ConfigurationException(
                f"Unknown type-inference strategy {type_inference_strategy}"
            )


def infer_type_info_no_types(method: Callable) -> InferredSignature:
    """Infers the method signature without incorporating type information.

    Args:
        method: The callable

    Returns:
        The inference result
    """
    if inspect.isclass(method) and hasattr(method, "__init__"):
        return infer_type_info_no_types(getattr(method, "__init__"))

    method_signature = signature(method)
    parameters: dict[str, type | None] = {}
    for param_name in method_signature.parameters:
        if param_name == "self":
            continue
        parameters[param_name] = Any  # type: ignore
    return_type: type | None = Any  # type: ignore

    return InferredSignature(
        signature=method_signature, parameters=parameters, return_type=return_type
    )


def infer_type_info_with_types(method: Callable) -> InferredSignature:
    """Infers the method signature while incorporating PEP484-style type information.

    Args:
        method: The callable

    Returns:
        The inference result
    """
    if inspect.isclass(method) and hasattr(method, "__init__"):
        return infer_type_info_with_types(getattr(method, "__init__"))

    method_signature = signature(method)
    parameters: dict[str, type | None] = {}
    hints = get_type_hints(method)
    for param_name in method_signature.parameters:
        if param_name == "self":
            continue
        hint = hints.get(param_name, Any)
        hint = wrap_var_param_type(hint, method_signature.parameters[param_name].kind)
        parameters[param_name] = hint

    return_type: type | None = hints.get("return", Any)

    return InferredSignature(
        signature=method_signature, parameters=parameters, return_type=return_type
    )
