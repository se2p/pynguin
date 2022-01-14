#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an access component to type inference strategies."""
from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Callable

from pynguin.typeinference.nonstrategy import NoTypeInferenceStrategy

if TYPE_CHECKING:
    from pynguin.typeinference.strategy import InferredSignature, TypeInferenceStrategy


# pylint: disable=too-few-public-methods
class TypeInference:
    """Provides access to type inference strategies."""

    def __init__(
        self,
        strategies: list[TypeInferenceStrategy] | None = None,
        strategy_names: list[str] | None = None,
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
        self._strategies: list[TypeInferenceStrategy] = _strategies

    @staticmethod
    def _initialise_strategies(
        strategy_names: list[str],
    ) -> list[TypeInferenceStrategy]:
        strategies: list[TypeInferenceStrategy] = []
        for strategy in strategy_names:
            try:
                module_path, class_name = strategy.rsplit(".", 1)
                module = importlib.import_module(module_path)
                strategies.append(getattr(module, class_name))
            except (ImportError, AttributeError) as exception:
                raise ImportError(strategy) from exception
        return strategies

    def infer_type_info(self, method: Callable) -> list[InferredSignature]:
        """Evaluates the type information for a callable.

        It returns a list of `InferredSignature`s that could be inferred for the
        given callable.

        Args:
            method: The callable we try to infer type information for

        Returns:
            A list of InferredSignature
        """
        method_types: list[InferredSignature] = []
        for strategy in self._strategies:
            method_types.append(strategy.infer_type_info(method))
        return method_types
