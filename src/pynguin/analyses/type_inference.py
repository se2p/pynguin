# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Implements type inference strategies."""

from abc import ABC, abstractmethod
import inspect
import logging
import string

from pynguin.analyses.module import TestCluster
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject
from pynguin.utils.llm import LLM, LLMProvider


_LOGGER = logging.getLogger(__name__)


class InferenceStrategy(ABC):
    """Abstract base class for all inference strategies that modify the test cluster with inferred types."""

    def __init__(self, test_cluster: TestCluster) -> None:
        """Initialise the strategy with a reference to the test cluster."""
        self._test_cluster = test_cluster

    @abstractmethod
    def infer_types(self) -> None:
        """Perform type inference and update the test cluster accordingly."""


class LLMInference(InferenceStrategy):
    """LLM based type inference strategy for a testcluster."""

    def __init__(self, test_cluster: TestCluster, provider: LLMProvider) -> None:
        """Initialise the strategy with a reference to the test cluster and an LLM."""
        self._model = LLM.create(provider)
        super().__init__(test_cluster)

    def infer_types(self) -> None:
        """Enriches the testcluster with type information using an LLM."""
        callables = self._test_cluster.function_data_for_accessibles
        _LOGGER.debug("started type inference with %s", callables)
        for callable_obj in callables:
            src_code = self._get_src_code(callable_obj)
            _LOGGER.debug("extracted %s", src_code)
            src_class_module = self._get_src_class(callable_obj)
            _LOGGER.debug("in class: %s", src_class_module)

    def _get_src_code(self, accessible: GenericCallableAccessibleObject) -> string:
        call = accessible.callable
        try:
            src_code = inspect.getsource(call)
        except (OSError, TypeError):
            _LOGGER.error(
                "Failed to retrieve source code for accessible",
            )
            return ""
        return src_code

    def _get_src_class_module(self, accessible: GenericCallableAccessibleObject):
        return accessible.owner.full_name

    def _build_prompt(self, src_code: string, class_module_name: string) -> string:
        return ""
