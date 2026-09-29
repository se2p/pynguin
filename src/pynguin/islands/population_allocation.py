#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Computes the per-island population size used by configuration validation
and island initialization.
"""  # noqa: D205

from __future__ import annotations

import pynguin.configuration as config


def compute_island_population_size(
    base_population: int,
    allocation: config.PopulationAllocation,
    num_islands: int,
    island_id: int,
) -> int:
    """Computes the population size assigned to a specific island.

    Args:
        base_population: The configured population size.
        allocation: The population allocation policy.
        num_islands: The total number of islands.
        island_id: The index of the island.

    Returns:
        The population size for this specific island.
    """
    if allocation is config.PopulationAllocation.FULL_PER_ISLAND:
        return base_population
    quotient, remainder = divmod(base_population, num_islands)
    return quotient + (1 if island_id < remainder else 0)


def minimum_island_population_size(
    base_population: int,
    allocation: config.PopulationAllocation,
    num_islands: int,
) -> int:
    """Computes the minimum population size assigned to any island.

    Args:
        base_population: The configured population size.
        allocation: The population allocation policy.
        num_islands: The total number of islands.

    Returns:
        The smallest population size assigned to an island.
    """
    if allocation is config.PopulationAllocation.FULL_PER_ISLAND:
        return base_population
    return base_population // num_islands
