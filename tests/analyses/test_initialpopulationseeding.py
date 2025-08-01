#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

import operator

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasefactory as tcf
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testfactory as tf

from pynguin.analyses import seeding
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import ModuleTestCluster
from pynguin.analyses.module import generate_test_cluster
from pynguin.ga.generationalgorithmfactory import TestSuiteGenerationAlgorithmFactory


@pytest.fixture
def seed_modules_path():
    return (
        Path(__file__).parent
        / ".."
        / "fixtures"
        / "seeding"
        / "initialpopulationseeding"
        / "seedmodules"
    )


@pytest.fixture
def triangle_test_cluster() -> ModuleTestCluster:
    return generate_test_cluster("tests.fixtures.examples.triangle")


@pytest.fixture
def dummy_test_cluster() -> ModuleTestCluster:
    return generate_test_cluster("tests.fixtures.seeding.initialpopulationseeding.dummycontainer")


@pytest.fixture
def constant_provider():
    return EmptyConstantProvider()


def test_get_testcases(constant_provider, seed_modules_path, triangle_test_cluster):
    config.configuration.module_name = "triangle"
    provider = seeding.InitialPopulationProvider(
        triangle_test_cluster,
        tf.TestFactory(triangle_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)

    assert len(provider) == 2


def test_get_seeded_testcase(constant_provider, seed_modules_path, triangle_test_cluster):
    config.configuration.module_name = "triangle"
    provider = seeding.InitialPopulationProvider(
        triangle_test_cluster,
        tf.TestFactory(triangle_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)

    seeded_testcase = provider.random_testcase()
    assert isinstance(seeded_testcase, dtc.DefaultTestCase)


@pytest.mark.parametrize(
    "module_name, position, result, testcase_pos",
    [
        pytest.param("primitiveseed", 2, "Floats are different!", 0),
        pytest.param("primitiveseed", 2, "Floats are equal!", 1),
        pytest.param("primitiveseed", 2, "Bools are equal!", 2),
        pytest.param("primitiveseed", 2, "Bools are different!", 3),
        pytest.param("primitiveseed", 1, "Is None!", 4),
        pytest.param("primitiveseed", 2, "Strings are different!", 5),
        pytest.param("primitiveseed", 2, "Bytes are different!", 6),
        pytest.param("collseed", 4, "not empty!", 0),
        pytest.param("collseed", 7, "not empty!", 1),
        pytest.param("collseed", 4, "not empty!", 2),
        pytest.param("collseed", 4, "not empty!", 3),
        pytest.param("nestedseed", 15, "not empty!", 0),
        pytest.param("collfuncseed", 1, "empty!", 0),
        pytest.param("collfuncseed", 1, "empty!", 1),
        pytest.param("collfuncseed", 3, "not empty!", 2),
        pytest.param("collfuncseed", 3, "not empty!", 3),
        pytest.param("collfuncseed", 1, "empty!", 4),
        pytest.param("classseed", 6, "not empty!", 0),
    ],
)
@mock.patch("pynguin.utils.randomness.choice")
def test_collect_different_types(  # noqa: PLR0917
    rand_mock,
    constant_provider,
    seed_modules_path,
    dummy_test_cluster,
    module_name,
    result,
    position,
    testcase_pos,
):
    config.configuration.module_name = module_name

    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster,
        tf.TestFactory(dummy_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)
    rand_mock.side_effect = operator.itemgetter(testcase_pos)

    seeded_testcase = provider.random_testcase()
    assert seeded_testcase is not None
    assert seeded_testcase.statements[position].assertions[0].object == result


@pytest.mark.parametrize(
    "position, num_assertions, testcase_pos",
    [
        pytest.param(1, 0, 0),
        pytest.param(0, 1, 1),
        pytest.param(0, 0, 2),
        pytest.param(0, 1, 3),
    ],
)
@mock.patch("pynguin.utils.randomness.choice")
def test_create_assertion(  # noqa: PLR0917
    rand_mock,
    constant_provider,
    seed_modules_path,
    dummy_test_cluster,
    num_assertions,
    position,
    testcase_pos,
):
    config.configuration.module_name = "assertseed"
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster,
        tf.TestFactory(dummy_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)
    rand_mock.side_effect = operator.itemgetter(testcase_pos)

    seeded_testcase = provider.random_testcase()
    assert len(seeded_testcase.statements[position].assertions) == num_assertions


@pytest.mark.parametrize(
    "module_name",
    [
        pytest.param("notprimseed"),
        pytest.param("wrongfunctionnameseed"),
        pytest.param("notknowncall"),
        pytest.param("wrongassignseed"),
    ],
)
def test_not_working_cases(constant_provider, seed_modules_path, dummy_test_cluster, module_name):
    config.configuration.module_name = module_name
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster,
        tf.TestFactory(dummy_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)

    assert len(provider) == 0


@mock.patch("pynguin.utils.randomness.choice")
def test_seeded_test_case_factory_no_delegation(
    rand_mock, constant_provider, seed_modules_path, dummy_test_cluster
):
    rand_mock.side_effect = operator.itemgetter(2)
    test_factory = tf.TestFactory(dummy_test_cluster, constant_provider)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster, test_factory, constant_provider
    )
    config.configuration.module_name = "primitiveseed"
    config.configuration.seeding.initial_population_seeding = True
    config.configuration.seeding.initial_population_data = seed_modules_path
    config.configuration.seeding.seeded_testcases_reuse_probability = 1.0
    provider.collect_testcases(seed_modules_path)
    delegate = tcf.RandomLengthTestCaseFactory(test_factory, dummy_test_cluster)
    test_case_factory = tcf.SeededTestCaseFactory(delegate, provider)

    seeded_testcase = test_case_factory.get_test_case()
    assert seeded_testcase.statements[2].assertions[0].object == "Bools are equal!"


@mock.patch("pynguin.utils.randomness.choice")
def test_seeded_test_case_factory_with_delegation(
    rand_mock, constant_provider, seed_modules_path, dummy_test_cluster
):
    rand_mock.side_effect = operator.itemgetter(2)  # pragma: no cover
    test_factory = tf.TestFactory(dummy_test_cluster, constant_provider)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster, test_factory, constant_provider
    )
    config.configuration.module_name = "primitiveseed"
    config.configuration.seeding.initial_population_seeding = True
    config.configuration.seeding.initial_population_data = seed_modules_path
    config.configuration.seeding.seeded_testcases_reuse_probability = 0.0
    provider.collect_testcases(seed_modules_path)
    delegate = tcf.RandomLengthTestCaseFactory(test_factory, dummy_test_cluster)
    delegate.get_test_case = MagicMock()
    test_case_factory = tcf.SeededTestCaseFactory(delegate, provider)
    test_case_factory.get_test_case()
    delegate.get_test_case.assert_called_once()


@pytest.mark.parametrize(
    "enabled, fac_type",
    [
        pytest.param(True, tcf.SeededTestCaseFactory),
        pytest.param(False, tcf.RandomLengthTestCaseFactory),
    ],
)
@mock.patch("pynguin.testcase.execution.TestCaseExecutor")
def test_algorithm_generation_factory(
    mock_class, constant_provider, dummy_test_cluster, enabled, fac_type
):
    config.configuration.seeding.initial_population_seeding = enabled
    config.configuration.algorithm = config.Algorithm.MIO
    tsfactory = TestSuiteGenerationAlgorithmFactory(
        mock_class.return_value, dummy_test_cluster, constant_provider
    )
    with mock.patch("pynguin.analyses.seeding.InitialPopulationProvider.__len__") as len_mock:
        len_mock.return_value = 1
        chromosome_factory = tsfactory._get_chromosome_factory(
            MagicMock(test_case_fitness_functions=[], test_suite_fitness_functions=[])
        )
    test_case_factory = chromosome_factory._test_case_factory
    assert type(test_case_factory) is fac_type


@mock.patch("ast.parse")
def test_module_not_readable(parse_mock, constant_provider, seed_modules_path, dummy_test_cluster):
    test_factory = tf.TestFactory(dummy_test_cluster, constant_provider)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster, test_factory, constant_provider
    )
    parse_mock.side_effect = BaseException
    provider.collect_testcases(seed_modules_path)

    assert len(provider) == 0


@mock.patch("pynguin.ga.testcasechromosome.TestCaseChromosome.mutate")
def test_initial_mutation(mutate_mock, constant_provider, seed_modules_path, dummy_test_cluster):
    config.configuration.seeding.initial_population_mutations = 2
    config.configuration.module_name = "primitiveseed"
    test_factory = tf.TestFactory(dummy_test_cluster, constant_provider)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster, test_factory, constant_provider
    )
    provider.collect_testcases(seed_modules_path)
    mutate_mock.assert_called()
