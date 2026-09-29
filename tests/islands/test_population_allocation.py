#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

import pynguin.configuration as config
from pynguin.islands.population_allocation import (
    compute_island_population_size,
    minimum_island_population_size,
)


def test_full_per_island_gives_every_island_the_full_population():
    for island_id in range(4):
        assert (
            compute_island_population_size(
                50, config.PopulationAllocation.FULL_PER_ISLAND, 4, island_id
            )
            == 50
        )


@pytest.mark.parametrize(
    ("population", "num_islands"),
    [(50, 4), (51, 4), (10, 3), (1, 5), (100, 7)],
)
def test_fixed_total_distributed_sums_to_the_base_population(population, num_islands):
    sizes = [
        compute_island_population_size(
            population, config.PopulationAllocation.FIXED_TOTAL_DISTRIBUTED, num_islands, island_id
        )
        for island_id in range(num_islands)
    ]
    assert sum(sizes) == population


def test_fixed_total_distributed_spreads_remainder_to_lowest_numbered_islands():
    sizes = [
        compute_island_population_size(
            10, config.PopulationAllocation.FIXED_TOTAL_DISTRIBUTED, 4, island_id
        )
        for island_id in range(4)
    ]
    assert sizes == [3, 3, 2, 2]


def test_minimum_island_population_size_full_per_island_is_the_base_population():
    assert minimum_island_population_size(50, config.PopulationAllocation.FULL_PER_ISLAND, 4) == 50


def test_minimum_island_population_size_fixed_total_distributed_is_the_floor_division():
    assert (
        minimum_island_population_size(10, config.PopulationAllocation.FIXED_TOTAL_DISTRIBUTED, 4)
        == 2
    )
