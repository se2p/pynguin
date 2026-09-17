#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Records which external classes a module should mock, keyed by class FQN."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pynguin.large_language_model.mock_generation.dependency_analyzer import (
    DependencyAnalyzer,
)

if TYPE_CHECKING:
    from pathlib import Path

    from pynguin.large_language_model.mock_generation.dependency_analyzer import (
        MockDecision,
    )


@dataclass
class MockParameter:
    """A configurable value in a mock template."""

    name: str
    param_type: str
    default_value: Any
    description: str


@dataclass
class MockMethodConfig:
    """Return-value/side-effect setup for one method of a mocked class."""

    method_name: str
    return_value_template: str
    parameters: list[MockParameter] = field(default_factory=list)
    side_effect: str | None = None


@dataclass(frozen=True)
class RaiseException:
    """A mutable-setup candidate that makes the mocked call raise a builtin exception.

    Used as a ``side_effect`` candidate: rendered as a bare exception name (e.g.
    ``mock.get.side_effect = KeyError``) so an error-handling branch guarded by
    ``except <name>`` is reached. Only builtin exceptions are used, so no import
    is needed in the generated test.
    """

    name: str


@dataclass
class MutableSetup:
    """A return-value assignment whose constant varies across tests.

    target: attribute chain after the mock variable, e.g.
    ``get.return_value.status_code``. candidates: the values to explore, seeded
    from the function's branch constants so the search covers each branch. A
    candidate may also be a :class:`RaiseException` marker for side-effect setups.
    """

    target: str
    candidates: list[Any]


@dataclass
class MockTemplate:
    """A mock for one class: its target FQN plus optional return-value hints."""

    dependency: str
    import_path: str
    mock_target: str
    method_configs: list[MockMethodConfig] = field(default_factory=list)
    setup_code: str = ""
    parameters: list[MockParameter] = field(default_factory=list)
    attribute_values: dict[str, Any] = field(default_factory=dict)
    # Raw proxy return-value setup lines, e.g. "mock.request.return_value.status = 200".
    # The leading placeholder name is renamed to the mock variable at render time.
    setup_lines: list[str] = field(default_factory=list)
    # Return-value assignments whose constant the search varies across tests.
    mutable_setups: list[MutableSetup] = field(default_factory=list)


class MockGenerator:
    """Runs the Dependency Analyzer and records the classes to mock.

    use_proxy: when True, unclassified classes are sent to the proxy-cache.
    """

    def __init__(self, *, use_proxy: bool = False) -> None:
        """Initialise the generator."""
        self._use_proxy = use_proxy
        self._mock_targets: set[str] = set()
        self._source_counts: dict[str, int] = {}

    @property
    def mock_targets(self) -> set[str]:
        """Class FQNs to mock, populated by generate_for_module."""
        return self._mock_targets

    @property
    def source_counts(self) -> dict[str, int]:
        """How many mock targets came from each source (rule / llm / ...)."""
        return self._source_counts

    def generate_for_module(
        self,
        module_path: Path,
        base_rules_cache_id: str | None = None,
        *,
        candidate_classes: list[type] | None = None,
    ) -> None:
        """Classify the module's external classes and record the mock targets.

        module_path: SUT source file. base_rules_cache_id: proxy rules set to use.
        candidate_classes: classes an untyped parameter may resolve to under type
        tracing; supplied only when type tracing is enabled so their boundaries
        are classified eagerly (no proxy calls during test generation).
        """
        analyzer = DependencyAnalyzer(
            module_path,
            rules_cache_id=base_rules_cache_id,
            use_proxy=self._use_proxy,
        )
        decisions = list(analyzer.analyze())
        if candidate_classes:
            decisions += self._classify_untyped_candidates(analyzer, module_path, candidate_classes)

        # Deduplicate by target (a class may be found via imports and via tracing).
        mock_by_target: dict[str, MockDecision] = {}
        for decision in decisions:
            if decision.decision == "mock" and decision.target not in mock_by_target:
                mock_by_target[decision.target] = decision
        self._mock_targets = set(mock_by_target)
        self._source_counts = dict(Counter(d.source for d in mock_by_target.values()))

    @staticmethod
    def _classify_untyped_candidates(
        analyzer: DependencyAnalyzer,
        module_path: Path,
        candidate_classes: list[type],
    ) -> list[MockDecision]:
        """Classify the classes an untyped parameter could resolve to."""
        from pynguin.large_language_model.mock_generation.untyped_param_analyzer import (  # noqa: PLC0415
            match_candidate_classes,
            untyped_param_attr_sets,
        )

        attr_sets = untyped_param_attr_sets(module_path.read_text(encoding="utf-8"))
        if not attr_sets:
            return []
        matched = match_candidate_classes(attr_sets, candidate_classes)
        pending = [(fqn, cls) for fqn, cls in matched.items()]
        return analyzer.classify_targets(pending)
