#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Client for the proxy-cache classify, generate-mock, and rules endpoints."""

from __future__ import annotations

import httpx

from pynguin.large_language_model.mock_generation.proxy_cache_resolver import (
    require_proxy_cache_url,
)

_TIMEOUT: float = 30.0


def classify_target(target: str, context: str = "") -> dict:
    """Classify a fully-qualified Python name as 'mock' or 'skip' via the proxy."""
    response = httpx.post(
        f"{require_proxy_cache_url()}/api/v1/pynguin/mock/classify",
        json={"target": target, "context": context},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def classify_targets_batch(targets: list[str], context: str = "") -> dict[str, dict]:
    """Classify several targets in one request; return {target: classify result}."""
    response = httpx.post(
        f"{require_proxy_cache_url()}/api/v1/pynguin/mock/classify-batch",
        json={"targets": targets, "context": context},
        timeout=90.0,
    )
    response.raise_for_status()
    return {r["target"]: r for r in response.json().get("results", [])}


def generate_mock_config(
    function_name: str,
    function_source: str,
    dependencies: list[dict],
    usage_context: str = "",
) -> dict:
    """Generate mock configurations for a function via the proxy."""
    response = httpx.post(
        f"{require_proxy_cache_url()}/api/v1/pynguin/mock/generate-mock",
        json={
            "function_name": function_name,
            "function_source": function_source,
            "dependencies": dependencies,
            "usage_context": usage_context,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()


def get_rules(versioned_id: str) -> dict:
    """Fetch a rules dict previously stored on the proxy-cache."""
    response = httpx.get(
        f"{require_proxy_cache_url()}/api/v1/pynguin/rules/{versioned_id}",
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("rules", payload)
