#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Tests for cache:
from unittest.mock import MagicMock

import pytest

import pynguin.ga.computations as ff


@pytest.fixture
def cache():
    return ff.ComputationCache(MagicMock())


def test_computation_cache_empty(cache):
    assert cache.get_fitness_functions() == []
    assert cache.get_coverage_functions() == []


def test_computation_cache_fitness(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = False
    cache.add_fitness_function(func)
    assert cache.get_fitness_functions() == [func]


def test_computation_cache_fitness_maximize(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = True
    with pytest.raises(AssertionError):
        cache.add_fitness_function(func)


def test_computation_cache_coverage(cache):
    func = MagicMock()
    cache.add_coverage_function(func)
    assert cache.get_coverage_functions() == [func]


def test_computation_cache_clone(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = False
    func.compute_fitness.return_value = 0
    cache.add_fitness_function(func)

    func2 = MagicMock()
    func2.compute_coverage.return_value = 1
    cache.add_coverage_function(func2)
    cache._chromosome.has_changed.return_value = False
    assert cache.get_coverage() == 1
    assert cache.get_fitness() == 0

    new = MagicMock()
    cloned = cache.clone(new)
    assert cloned.get_fitness_functions() == [func]
    assert cloned.get_coverage_functions() == [func2]
    assert cloned._is_covered_cache[func] is True
    assert cloned._fitness_cache[func] == 0
    assert cloned._coverage_cache[func2] == 1


def test_computation_cache_fitness_cache(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = False
    func.compute_fitness.return_value = 0
    cache.add_fitness_function(func)
    cache._chromosome.has_changed.return_value = False

    assert cache.get_fitness() == 0
    assert cache.get_fitness() == 0
    assert func.compute_fitness.call_count == 1


def test_computation_cache_fitness_cache_changed(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = False
    func.compute_fitness.return_value = 0
    cache.add_fitness_function(func)
    cache._chromosome.changed = True
    assert cache.get_fitness() == 0
    cache._chromosome.changed = True
    assert cache.get_fitness() == 0
    assert func.compute_fitness.call_count == 2


def test_computation_cache_fitness_infers_is_covered(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = False
    func.compute_fitness.return_value = 0
    cache.add_fitness_function(func)
    cache._chromosome.has_changed.return_value = False

    assert cache.get_fitness() == 0
    assert cache.get_is_covered(func) is True
    assert func.compute_fitness.call_count == 1
    assert func.compute_is_covered.call_count == 0


def test_computation_cache_fitness_compute_order(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = False
    func.compute_fitness.return_value = 0
    func.compute_is_covered.return_value = True
    cache.add_fitness_function(func)
    cache._chromosome.has_changed.return_value = False

    assert cache.get_is_covered(func) is True
    assert cache.get_fitness() == 0
    assert func.compute_fitness.call_count == 1
    assert func.compute_is_covered.call_count == 1


def test_computation_cache_coverage_cache(cache):
    func = MagicMock()
    func.compute_coverage.return_value = 1
    cache.add_coverage_function(func)
    cache._chromosome.has_changed.return_value = False

    assert cache.get_coverage() == 1
    assert cache.get_coverage() == 1
    assert func.compute_coverage.call_count == 1


def test_computation_cache_coverage_cache_changed(cache):
    func = MagicMock()
    func.compute_coverage.return_value = 1
    cache.add_coverage_function(func)
    cache._chromosome.changed = True

    assert cache.get_coverage() == 1
    cache._chromosome.changed = True
    assert cache.get_coverage() == 1
    assert func.compute_coverage.call_count == 2


def test_computation_cache_coverage_mean(cache):
    func = MagicMock()
    func.compute_coverage.return_value = 1
    func2 = MagicMock()
    func2.compute_coverage.return_value = 0
    cache.add_coverage_function(func)
    cache.add_coverage_function(func2)

    assert cache.get_coverage() == 0.5


def test_computation_cache_coverage_for(cache):
    func = MagicMock()
    func.compute_coverage.return_value = 1
    func2 = MagicMock()
    func2.compute_coverage.return_value = 0
    cache._chromosome.has_changed.return_value = False
    cache.add_coverage_function(func)
    cache.add_coverage_function(func2)

    assert cache.get_coverage_for(func) == 1
    assert func.compute_coverage.call_count == 1
    assert func2.compute_coverage.call_count == 0


def test_computation_cache_fitness_for(cache):
    func = MagicMock()
    func.is_maximisation_function.return_value = False
    func.compute_fitness.return_value = 0
    func.compute_is_covered.return_value = True
    func2 = MagicMock()
    func2.is_maximisation_function.return_value = False
    func2.compute_fitness.return_value = 0
    func2.compute_is_covered.return_value = True
    cache.add_fitness_function(func)
    cache.add_fitness_function(func2)

    assert cache.get_fitness_for(func) == 0
    assert func.compute_fitness.call_count == 1
    assert func2.compute_fitness.call_count == 0
