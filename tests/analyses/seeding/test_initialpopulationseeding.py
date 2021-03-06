#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import os
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.analyses.seeding.initialpopulationseeding as ips
import pynguin.configuration as config
import pynguin.ga.testcasefactory as tcf
import pynguin.generator as gen
import pynguin.testcase.defaulttestcase as dtc
from pynguin.generation.generationalgorithmfactory import (
    TestSuiteGenerationAlgorithmFactory,
)
from pynguin.setup.testcluster import TestCluster
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.testfactory import TestFactory


@pytest.fixture()
def seed_modules_path():
    dummy_test_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "fixtures",
        "seeding",
        "initialpopulationseeding",
        "seedmodules",
    )
    return dummy_test_file


@pytest.fixture()
def clear_ips_instance():
    ips.initialpopulationseeding._testcases = []
    ips.initialpopulationseeding.test_cluster = TestCluster()


@pytest.fixture()
def triangle_test_cluster() -> TestCluster:
    test_cluster = TestClusterGenerator(
        "tests.fixtures.examples.triangle"
    ).generate_cluster()
    return test_cluster


@pytest.fixture()
def dummy_test_cluster() -> TestCluster:
    test_cluster = TestClusterGenerator(
        "tests.fixtures.seeding.initialpopulationseeding.dummycontainer"
    ).generate_cluster()
    return test_cluster


def test_get_testcases(clear_ips_instance, seed_modules_path, triangle_test_cluster):
    ips.initialpopulationseeding.test_cluster = triangle_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "triangleseed.py")
    ips.initialpopulationseeding.collect_testcases(init_pop_file)

    assert ips.initialpopulationseeding.has_tests
    assert len(ips.initialpopulationseeding._testcases) == 2


def test_get_seeded_testcase(
    clear_ips_instance, seed_modules_path, triangle_test_cluster
):
    ips.initialpopulationseeding.test_cluster = triangle_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "triangleseed.py")
    ips.initialpopulationseeding.collect_testcases(init_pop_file)

    seeded_testcase = ips.initialpopulationseeding.seeded_testcase
    assert isinstance(seeded_testcase, dtc.DefaultTestCase)


@pytest.mark.parametrize(
    "file_name, position, result, testcase_pos",
    [
        pytest.param("primitiveseed.py", 2, "Floats are different!", 0),
        pytest.param("primitiveseed.py", 2, "Floats are equal!", 1),
        pytest.param("primitiveseed.py", 2, "Bools are equal!", 2),
        pytest.param("primitiveseed.py", 2, "Bools are different!", 3),
        pytest.param("primitiveseed.py", 1, "Is None!", 4),
        pytest.param("primitiveseed.py", 2, "Strings are different!", 5),
        pytest.param("primitiveseed.py", 2, "Bytes are different!", 6),
        pytest.param("collseed.py", 4, "not empty!", 0),
        pytest.param("collseed.py", 7, "not empty!", 1),
        pytest.param("collseed.py", 4, "not empty!", 2),
        pytest.param("collseed.py", 4, "not empty!", 3),
        pytest.param("nestedseed.py", 15, "not empty!", 0),
        pytest.param("collfuncseed.py", 1, "empty!", 0),
        pytest.param("collfuncseed.py", 1, "empty!", 1),
        pytest.param("collfuncseed.py", 3, "not empty!", 2),
        pytest.param("collfuncseed.py", 4, "not empty!", 3),
        pytest.param("collfuncseed.py", 1, "empty!", 4),
        pytest.param("classseed.py", 6, "not empty!", 0),
    ],
)
@mock.patch("pynguin.utils.randomness.next_int")
def test_collect_different_types(
    rand_mock,
    clear_ips_instance,
    seed_modules_path,
    dummy_test_cluster,
    file_name,
    result,
    position,
    testcase_pos,
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, file_name)
    ips.initialpopulationseeding.collect_testcases(init_pop_file)
    rand_mock.return_value = testcase_pos

    seeded_testcase = ips.initialpopulationseeding.seeded_testcase
    assert seeded_testcase is not None
    assert next(iter(seeded_testcase.statements[position].assertions)).value == result


@pytest.mark.parametrize(
    "position, num_assertions, testcase_pos",
    [
        pytest.param(1, 0, 0),
        pytest.param(0, 1, 1),
        pytest.param(0, 0, 2),
        pytest.param(0, 1, 3),
    ],
)
@mock.patch("pynguin.utils.randomness.next_int")
def test_create_assertion(
    rand_mock,
    clear_ips_instance,
    seed_modules_path,
    dummy_test_cluster,
    num_assertions,
    position,
    testcase_pos,
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "assertseed.py")
    ips.initialpopulationseeding.collect_testcases(init_pop_file)
    rand_mock.return_value = testcase_pos

    seeded_testcase = ips.initialpopulationseeding.seeded_testcase
    assert len(seeded_testcase.statements[position].assertions) == num_assertions


@pytest.mark.parametrize(
    "file_name",
    [
        pytest.param("notprimitiveseed.py"),
        pytest.param("wrongfunctionnameseed.py"),
        pytest.param("notknowncall.py"),
        pytest.param("wrongassignseed.py"),
    ],
)
def test_not_working_cases(
    clear_ips_instance, seed_modules_path, dummy_test_cluster, file_name
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, file_name)
    ips.initialpopulationseeding.collect_testcases(init_pop_file)

    assert not ips.initialpopulationseeding._testcases


@mock.patch("pynguin.utils.randomness.next_int")
def test_generator_with_init_pop_seeding(
    rand_mock, clear_ips_instance, seed_modules_path, dummy_test_cluster
):
    rand_mock.return_value = 2
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    config.configuration.initial_population_seeding = True
    config.configuration.initial_population_data = os.path.join(
        seed_modules_path, "primitiveseed.py"
    )
    gen.set_configuration(config.configuration)
    gen._setup_initial_population_seeding(dummy_test_cluster)
    seeded_testcase = ips.initialpopulationseeding.seeded_testcase
    assert ips.initialpopulationseeding.has_tests
    assert (
        next(iter(seeded_testcase.statements[2].assertions)).value == "Bools are equal!"
    )


@mock.patch("pynguin.utils.randomness.next_int")
def test_seeded_test_case_factory_no_delegation(
    rand_mock, clear_ips_instance, seed_modules_path, dummy_test_cluster
):
    rand_mock.return_value = 2
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "primitiveseed.py")
    config.configuration.initial_population_seeding = True
    config.configuration.initial_population_data = init_pop_file
    config.configuration.seeded_testcases_reuse_probability = 1.0
    ips.initialpopulationseeding.collect_testcases(init_pop_file)
    test_factory = TestFactory(dummy_test_cluster)
    delegate = tcf.RandomLengthTestCaseFactory(test_factory)
    test_case_factory = tcf.SeededTestCaseFactory(delegate, test_factory)

    seeded_testcase = test_case_factory.get_test_case()
    assert (
        next(iter(seeded_testcase.statements[2].assertions)).value == "Bools are equal!"
    )


@mock.patch("pynguin.utils.randomness.next_int")
def test_seeded_test_case_factory_with_delegation(
    rand_mock, clear_ips_instance, seed_modules_path, dummy_test_cluster
):
    rand_mock.return_value = 2
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "primitiveseed.py")
    config.configuration.initial_population_seeding = True
    config.configuration.initial_population_data = init_pop_file
    config.configuration.seeded_testcases_reuse_probability = 0.0
    ips.initialpopulationseeding.collect_testcases(init_pop_file)
    test_factory = TestFactory(dummy_test_cluster)
    delegate = tcf.RandomLengthTestCaseFactory(test_factory)
    delegate.get_test_case = MagicMock()
    test_case_factory = tcf.SeededTestCaseFactory(delegate, test_factory)
    test_case_factory.get_test_case()
    delegate.get_test_case.assert_called_once()


@pytest.mark.parametrize(
    "enabled, fac_type",
    [
        pytest.param(True, tcf.SeededTestCaseFactory),
        pytest.param(False, tcf.RandomLengthTestCaseFactory),
    ],
)
@mock.patch("pynguin.testcase.execution.testcaseexecutor.TestCaseExecutor")
def test_algorithm_generation_factory(
    mock_class, dummy_test_cluster, enabled, fac_type
):
    config.configuration.initial_population_seeding = enabled
    tsfactory = TestSuiteGenerationAlgorithmFactory(
        mock_class.return_value, dummy_test_cluster
    )
    chromosome_factory = tsfactory._get_chromosome_factory()
    test_case_factory = (
        chromosome_factory.test_case_chromosome_factory._test_case_factory
    )
    assert type(test_case_factory) == fac_type


@mock.patch("ast.parse")
def test_module_not_readable(parse_mock, clear_ips_instance, seed_modules_path):
    parse_mock.side_effect = BaseException
    init_pop_file = os.path.join(seed_modules_path, "primitiveseed.py")
    ips.initialpopulationseeding.collect_testcases(init_pop_file)

    assert not ips.initialpopulationseeding._testcases


@mock.patch("pynguin.ga.testcasechromosome.TestCaseChromosome.mutate")
def test_initial_mutation(
    mutate_mock, clear_ips_instance, seed_modules_path, dummy_test_cluster
):
    config.configuration.initial_population_mutations = 2
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "primitiveseed.py")
    ips.initialpopulationseeding.collect_testcases(init_pop_file)
    mutate_mock.assert_called()
