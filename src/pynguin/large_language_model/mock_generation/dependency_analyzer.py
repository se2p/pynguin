#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Classifies the external classes a module uses as 'mock', 'skip', or 'unknown'.

Each candidate is a fully-qualified class name (target).  Classification order,
first match wins: exception class -> skip, standard library -> skip, heuristic
rule -> mock, proxy-cache (LLM) -> mock/skip, otherwise unknown.
"""

from __future__ import annotations

import ast
import importlib
import json
import logging
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

from pynguin.large_language_model.mock_generation import llm_classifier_client

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)


@dataclass
class MockDecision:
    """Classification result for a single class target."""

    target: str  # fully-qualified class name
    decision: Literal["mock", "skip", "unknown"]
    reason: str
    source: Literal["rule", "stdlib", "local", "exception", "llm"]
    confidence: float


class HeuristicRules:
    """Maps a class target to a mock reason, produced by MockRuleGenerator."""

    def __init__(self, rules_path: Path | None = None) -> None:
        """rules_path: optional local rules JSON; empty when omitted."""
        data = (
            json.loads(rules_path.read_text(encoding="utf-8"))
            if rules_path is not None and rules_path.exists()
            else {}
        )
        self.targets: dict[str, str] = self._parse(data)

    @classmethod
    def from_proxy_cache(cls, versioned_id: str) -> HeuristicRules:
        """Load a rules set stored on the proxy-cache under *versioned_id*."""
        instance = cls.__new__(cls)
        instance.targets = cls._parse(llm_classifier_client.get_rules(versioned_id))
        return instance

    @staticmethod
    def _parse(data: dict) -> dict[str, str]:
        """Extract ``{target: reason}`` for mock entries from a rules dict."""
        targets: dict[str, str] = {}
        for entry in data.get("targets", []):
            if isinstance(entry, dict) and entry.get("decision") == "mock":
                target = entry.get("target")
                if target:
                    targets[target] = entry.get("reason", "mock-rule-generator")
        return targets

    def match(self, target: str) -> str | None:
        """Reason if *target* is a mock rule, else None."""
        return self.targets.get(target)


class DependencyAnalyzer:
    """Extracts the external classes a module uses and classifies each one."""

    def __init__(
        self,
        module_path: Path,
        heuristic_rules: HeuristicRules | None = None,
        *,
        rules_cache_id: str | None = None,
        use_proxy: bool = False,
    ) -> None:
        """module_path: SUT source file; rules_cache_id: proxy-cache rules set to load."""
        self._module_path = module_path
        self._use_proxy = use_proxy
        if heuristic_rules is not None:
            self._rules = heuristic_rules
        elif rules_cache_id:
            self._rules = self._load_rules(rules_cache_id)
        else:
            self._rules = HeuristicRules()

    # Public API

    def analyze(self) -> list[MockDecision]:
        """Return one MockDecision per unique external class used by the module."""
        source = self._module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(self._module_path))
        pairs: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for module, name in self._extract_candidates(tree):
            target, obj = self._resolve(module, name)
            if target in seen or (obj is not None and not isinstance(obj, type)):
                continue
            seen.add(target)
            pairs.append((target, obj))
        return self._classify_all(pairs)

    def classify_targets(self, targets: list[tuple[str, Any]]) -> list[MockDecision]:
        """Classify externally-supplied (fqn, class) candidates.

        Args:
            targets: (canonical FQN, class object) pairs to classify.
        """
        pairs: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for target, obj in targets:
            if target in seen:
                continue
            seen.add(target)
            pairs.append((target, obj))
        return self._classify_all(pairs)

    # Candidate extraction

    @staticmethod
    def _extract_candidates(tree: ast.Module) -> list[tuple[str, str]]:
        """(module, name) pairs from absolute imports and module-qualified uses."""
        module_aliases: dict[str, str] = {}
        candidates: list[tuple[str, str]] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_aliases[alias.asname or alias.name.split(".")[0]] = alias.name
            # Relative imports are the SUT's own modules, treated as local.
            elif (
                isinstance(node, ast.ImportFrom)
                and not node.level
                and node.module
                and node.module != "__future__"
            ):
                candidates += [(node.module, a.name) for a in node.names]

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in module_aliases
            ):
                candidates.append((module_aliases[node.value.id], node.attr))

        return candidates

    @staticmethod
    def _resolve(module: str, name: str) -> tuple[str, Any]:
        """Resolve (module, name) to its canonical FQN and object; object None on failure."""
        try:
            obj = getattr(importlib.import_module(module), name)
        except Exception:  # noqa: BLE001
            return f"{module}.{name}", None
        defining = getattr(obj, "__module__", None)
        obj_name = getattr(obj, "__name__", name)
        return (f"{defining}.{obj_name}" if defining else f"{module}.{name}"), obj

    # Classification

    def _classify_local(self, target: str, obj: Any) -> MockDecision | None:
        """Deterministic classification (exception/stdlib/rule); None if proxy-cache needed."""
        if isinstance(obj, type) and issubclass(obj, BaseException):
            return MockDecision(target, "skip", "Exception class", "exception", 1.0)
        if target.split(".", 1)[0] in sys.stdlib_module_names:
            return MockDecision(target, "skip", "Standard library", "stdlib", 1.0)
        reason = self._rules.match(target)
        if reason is not None:
            return MockDecision(target, "mock", reason, "rule", 0.9)
        return None

    def _classify(self, target: str, obj: Any) -> MockDecision:
        """Classify a single class *target* (with its resolved *obj* when available)."""
        local = self._classify_local(target, obj)
        if local is not None:
            return local
        if self._use_proxy:
            proxy = self._classify_via_proxy(target)
            if proxy is not None:
                return proxy
        return MockDecision(target, "unknown", "Unclassified external class", "llm", 0.0)

    def _classify_all(self, pairs: list[tuple[str, Any]]) -> list[MockDecision]:
        """Classify many candidates, batching the proxy-cache calls into one request."""
        local: dict[str, MockDecision] = {}
        proxy_needed: list[str] = []
        for target, obj in pairs:
            decision = self._classify_local(target, obj)
            if decision is not None:
                local[target] = decision
            else:
                proxy_needed.append(target)

        proxy = self._classify_via_proxy_batch(proxy_needed) if self._use_proxy else {}

        decisions: list[MockDecision] = []
        for target, _obj in pairs:
            decisions.append(
                local.get(target)
                or proxy.get(target)
                or MockDecision(target, "unknown", "Unclassified external class", "llm", 0.0)
            )
        return decisions

    @staticmethod
    def _classify_via_proxy_batch(targets: list[str]) -> dict[str, MockDecision]:
        """Batch-classify *targets* via the proxy-cache; empty dict on connection/HTTP error."""
        if not targets:
            return {}
        try:
            results = llm_classifier_client.classify_targets_batch(targets)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Proxy batch classify unavailable (%d): %s", len(targets), exc)
            return {}
        return {
            target: MockDecision(
                target,
                result.get("decision", "unknown"),
                result.get("reason", ""),
                "llm",
                float(result.get("confidence", 0.5)),
            )
            for target, result in results.items()
        }

    @staticmethod
    def _classify_via_proxy(target: str) -> MockDecision | None:
        """MockDecision from the proxy-cache, or None on connection/HTTP error."""
        try:
            result = llm_classifier_client.classify_target(target)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Proxy classify unavailable for %r: %s", target, exc)
            return None
        return MockDecision(
            target,
            result.get("decision", "unknown"),
            result.get("reason", ""),
            "llm",
            float(result.get("confidence", 0.5)),
        )

    @staticmethod
    def _load_rules(rules_cache_id: str) -> HeuristicRules:
        """Load proxy-cache rules, falling back to empty rules on error."""
        try:
            return HeuristicRules.from_proxy_cache(rules_cache_id)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Could not load rules %r (%s); using empty rules", rules_cache_id, exc)
            return HeuristicRules()
