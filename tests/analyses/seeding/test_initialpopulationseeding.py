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


def test_get_testcases(
    clear_ips_instance, seed_modules_path, triangle_test_cluster
):
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
    "file_name, position, result",
    [
        pytest.param("floatseed.py", 2, "Floats are different!"),
        pytest.param("negativefloatseed.py", 2, "Floats are equal!"),
        pytest.param("boolseed.py", 2, "Bools are equal!"),
        pytest.param("negatedboolseed.py", 2, "Bools are different!"),
        pytest.param("noneseed.py", 1, "Is None!"),
        pytest.param("stringseed.py", 2, "Strings are different!")
    ]
)
def test_collect_different_types(
    clear_ips_instance, seed_modules_path, dummy_test_cluster, file_name, result, position
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, file_name)
    ips.initialpopulationseeding.collect_testcases(init_pop_file)

    seeded_testcase = ips.initialpopulationseeding.seeded_testcase
    assert seeded_testcase is not None
    assert (
        next(iter(seeded_testcase.statements[position].assertions)).value
        == result
    )


@pytest.mark.parametrize(
    "file_name",
    [
        pytest.param("notprimitiveseed.py"),
        pytest.param("wrongfunctionnameseed.py")
    ]
)
def test_not_working_cases(
    clear_ips_instance, seed_modules_path, dummy_test_cluster, file_name
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, file_name)
    ips.initialpopulationseeding.collect_testcases(init_pop_file)

    assert not ips.initialpopulationseeding._testcases


def test_generator_with_init_pop_seeding(
    clear_ips_instance, seed_modules_path, dummy_test_cluster
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    config.configuration.initial_population_seeding = True
    config.configuration.initial_population_data = os.path.join(
        seed_modules_path, "boolseed.py"
    )
    generator = gen.Pynguin(config.configuration)
    generator._setup_initial_population_seeding(dummy_test_cluster)
    seeded_testcase = ips.initialpopulationseeding.seeded_testcase
    assert ips.initialpopulationseeding.has_tests
    assert (
        next(iter(seeded_testcase.statements[2].assertions)).value == "Bools are equal!"
    )


def test_seeded_test_case_factory_no_delegation(
    clear_ips_instance, seed_modules_path, dummy_test_cluster
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "boolseed.py")
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


def test_seeded_test_case_factory_with_delegation(
    clear_ips_instance, seed_modules_path, dummy_test_cluster
):
    ips.initialpopulationseeding.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "boolseed.py")
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
        pytest.param(False, tcf.RandomLengthTestCaseFactory)
    ]
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
