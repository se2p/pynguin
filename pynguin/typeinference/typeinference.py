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
"""Provides an access component to type inference strategies."""
import importlib
from typing import Callable, List, Optional

from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy
from pynguin.typeinference.strategy import InferredSignature, TypeInferenceStrategy


# pylint: disable=too-few-public-methods
class TypeInference:
    """Provides access to type inference strategies."""

    def __init__(
        self,
        strategies: Optional[List[TypeInferenceStrategy]] = None,
        strategy_names: Optional[List[str]] = None,
    ) -> None:
        """Creates the type inference object.

        The parameters are mutually exclusive, either use one of them or none.  The
        `strategies` parameter expects a list of already initialised type-inference
        strategies, the `strategy_names` parameter expects a list of fully-qualified
        class names (each class needs to extend `TypeInferenceStrategy`) that will be
        initialised on demand.  An ImportError is raised if the initialisation was not
        successful.

        If neither parameter is given, a default strategy will be initialised and used.

        Args:
            strategies: An optional list of already initialised strategies
            strategy_names: An optional list of fully-qualified strategy names
        """
        if strategies:
            _strategies = strategies
        elif strategy_names:
            _strategies = self._initialise_strategies(strategy_names)
        else:
            _strategies = [NoTypeInferenceStrategy()]
        self._strategies: List[TypeInferenceStrategy] = _strategies

    @staticmethod
    def _initialise_strategies(
        strategy_names: List[str],
    ) -> List[TypeInferenceStrategy]:
        strategies: List[TypeInferenceStrategy] = []
        for strategy in strategy_names:
            try:
                module_path, class_name = strategy.rsplit(".", 1)
                module = importlib.import_module(module_path)
                strategies.append(getattr(module, class_name))
            except (ImportError, AttributeError):
                raise ImportError(strategy)
        return strategies

    def infer_type_info(self, method: Callable) -> List[InferredSignature]:
        """Evaluates the type information for a callable.

        It returns a list of `InferredSignature`s that could be inferred for the
        given callable.

        Args:
            method: The callable we try to infer type information for

        Returns:
            A list of InferredSignature
        """
        method_types: List[InferredSignature] = []
        for strategy in self._strategies:
            method_types.append(strategy.infer_type_info(method))
        return method_types
