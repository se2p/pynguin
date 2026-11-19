#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import importlib
import itertools
from logging import Logger
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import libcst as cst
import pytest

import pynguin.configuration as config
import pynguin.ga.algorithms.dynamosaalgorithm as dyna
import pynguin.ga.generationalgorithmfactory as gaf
from pynguin.analyses.module import generate_test_cluster
from pynguin.ga.algorithms.speciation import SpeciationOptions, SpeciesAssigner
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    from pynguin.instrumentation.tracer import SubjectProperties


def _chromosome(*lines: str) -> tcc.TestCaseChromosome:
    chromosome = MagicMock()
    chromosome.test_case.statements.return_value = [
        SimpleNamespace(node=cst.parse_statement(line)) for line in lines
    ]
    return cast("tcc.TestCaseChromosome", chromosome)


@pytest.fixture
def mating_algorithm() -> tuple[dyna.DynaMOSAAlgorithm, list[Any]]:
    a_1, a_2, b_1 = _chromosome("a()"), _chromosome("a()"), _chromosome("b()")
    algorithm = dyna.DynaMOSAAlgorithm()
    algorithm._population = [a_1, b_1, a_2]
    algorithm._species_assigner = SpeciesAssigner(config.SpeciationMetric.METHOD_CALL_JACCARD, 0.5)
    algorithm._species_assigner.assign(algorithm._population, generation=0)
    algorithm._speciation_options = SpeciationOptions()
    selection = MagicMock()
    selection.select.side_effect = lambda population: [population[-1]]
    algorithm._selection_function = selection
    config.configuration.search_algorithm.speciation_restrict_mating = True
    return algorithm, [a_1, a_2, b_1]


def test_select_mate_restricted_to_species(mating_algorithm):
    algorithm, (a_1, a_2, _) = mating_algorithm
    assert algorithm._select_mate(a_1) is a_2
    algorithm._selection_function.select.assert_called_once_with([a_1, a_2])


def test_select_mate_singleton_species_uses_whole_population(mating_algorithm):
    algorithm, (_, a_2, b_1) = mating_algorithm
    assert algorithm._select_mate(b_1) is a_2
    algorithm._selection_function.select.assert_called_once_with(algorithm._population)


def test_select_mate_unassigned_parent_uses_whole_population(mating_algorithm):
    algorithm, _ = mating_algorithm
    stranger = _chromosome("a()")
    algorithm._select_mate(stranger)
    algorithm._selection_function.select.assert_called_once_with(algorithm._population)


@pytest.mark.parametrize("restricted, selecting", [(False, True), (True, False)])
def test_select_mate_unrestricted(mating_algorithm, restricted, selecting):
    algorithm, (a_1, _, _) = mating_algorithm
    config.configuration.search_algorithm.speciation_restrict_mating = restricted
    if not selecting:
        algorithm._speciation_options = None
    algorithm._select_mate(a_1)
    algorithm._selection_function.select.assert_called_once_with(algorithm._population)


def test_select_mate_without_speciation():
    algorithm = dyna.DynaMOSAAlgorithm()
    algorithm._population = [MagicMock(), MagicMock()]
    algorithm._selection_function = MagicMock()
    algorithm._selection_function.select.return_value = [algorithm._population[1]]
    assert algorithm._select_mate(algorithm._population[0]) is algorithm._population[1]


def test_record_species_statistics(monkeypatch):
    recorded: dict[RuntimeVariable, Any] = {}
    monkeypatch.setattr(
        dyna.stat,
        "set_output_variable_for_runtime_variable",
        recorded.__setitem__,
    )
    algorithm = dyna.DynaMOSAAlgorithm()
    algorithm._population = [_chromosome("a()"), _chromosome("a()"), _chromosome("b()")]
    algorithm._species_assigner = SpeciesAssigner(config.SpeciationMetric.METHOD_CALL_JACCARD, 0.5)
    algorithm._species_assigner.assign(algorithm._population, generation=0)
    algorithm._population.append(_chromosome("c()"))  # Unassigned, e.g. an LLM test.
    algorithm._protected_individuals = 3
    algorithm._protected_species = 1
    algorithm._record_species_statistics()
    assert recorded == {
        RuntimeVariable.SpeciesCountTimeline: 2,
        RuntimeVariable.LargestSpeciesShareTimeline: 0.5,
        RuntimeVariable.ProtectedIndividualsTimeline: 3,
        RuntimeVariable.ProtectedSpeciesTimeline: 1,
        RuntimeVariable.SpeciesFounded: 2,
    }


def _run_dynamosa(
    subject_properties: SubjectProperties,
    module_name: str = "tests.fixtures.examples.queue",
    **speciation: Any,
) -> tuple[dyna.DynaMOSAAlgorithm, list[str]]:
    config.configuration.algorithm = config.Algorithm.DYNAMOSA
    config.configuration.stopping.maximum_iterations = 6
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.population = 6
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    for name, value in speciation.items():
        setattr(config.configuration.search_algorithm, name, value)
    randomness.RNG.seed(42)
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)
        executor = TestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(module_name)
        algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        assert isinstance(algorithm, dyna.DynaMOSAAlgorithm)
        algorithm._logger = MagicMock(Logger)
        suite = algorithm.generate_tests()
    return algorithm, [chromosome.test_case.to_code() for chromosome in suite.test_case_chromosomes]


_GRID = list(
    itertools.product(
        list(config.SpeciationMetric),  # metric
        [1.0, 0.3],  # max species share
        [False, True],  # restrict mating
        [False, True],  # fitness sharing
        [0, 2],  # min survivors
        [0, 2],  # newborn protection
    )
)


@pytest.mark.parametrize(
    "metric, share, mating, sharing, min_survivors, newborn",
    _GRID,
)
def test_integrate_dynamosa_speciation_grid(  # noqa: PLR0917
    subject_properties: SubjectProperties,
    metric,
    share,
    mating,
    sharing,
    min_survivors,
    newborn,
):
    algorithm, _ = _run_dynamosa(
        subject_properties,
        speciation=True,
        speciation_metric=metric,
        speciation_threshold=0.4,
        speciation_max_species_share=share,
        speciation_restrict_mating=mating,
        speciation_fitness_sharing=sharing,
        speciation_min_survivors=min_survivors,
        speciation_newborn_protection=newborn,
    )
    assert algorithm._species_assigner is not None
    assert algorithm._species_assigner.number_of_species_founded >= 1
    population_size = config.configuration.search_algorithm.population
    assert len(algorithm._population) >= min(population_size, 1)


@pytest.mark.parametrize("metric", list(config.SpeciationMetric))
def test_integrate_dynamosa_speciation_defaults_equal_plain_dynamosa(
    subject_properties: SubjectProperties, metric
):
    _, plain = _run_dynamosa(subject_properties)
    algorithm, speciated = _run_dynamosa(
        subject_properties, speciation=True, speciation_metric=metric
    )
    assert algorithm._speciation_options is not None
    assert speciated == plain


def test_integrate_dynamosa_track_only_equals_plain_dynamosa(subject_properties: SubjectProperties):
    _, plain = _run_dynamosa(subject_properties)
    algorithm, tracked = _run_dynamosa(
        subject_properties,
        speciation_track_only=True,
        speciation_max_species_share=0.1,
        speciation_restrict_mating=True,
    )
    assert algorithm._species_assigner is not None
    assert algorithm._speciation_options is None
    assert tracked == plain


def test_integrate_dynamosa_without_speciation_has_no_assigner(
    subject_properties: SubjectProperties,
):
    algorithm, _ = _run_dynamosa(subject_properties)
    assert algorithm._species_assigner is None


def test_integrate_dynamosa_speciation_rejects_invalid_options(
    subject_properties: SubjectProperties,
):
    with pytest.raises(ConfigurationException, match="share"):
        _run_dynamosa(subject_properties, speciation=True, speciation_max_species_share=0.0)
