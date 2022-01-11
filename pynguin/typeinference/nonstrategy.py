#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a strategy that never does any type inference."""
import inspect
from typing import Callable, Dict, Optional

from pynguin.typeinference.strategy import InferredSignature, TypeInferenceStrategy


# pylint: disable=too-few-public-methods
class NoTypeInferenceStrategy(TypeInferenceStrategy):
    """Provides a strategy that never does any type inference."""

    def infer_type_info(self, method: Callable) -> InferredSignature:
        signature = inspect.signature(method)
        parameters: Dict[str, Optional[type]] = {}
        for param_name in signature.parameters:
            if param_name == "self":
                continue
            parameters[param_name] = None
        return_type: Optional[type] = None

        return InferredSignature(
            signature=signature, parameters=parameters, return_type=return_type
        )
