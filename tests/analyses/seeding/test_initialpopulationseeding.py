import os
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.analyses.seeding.initialpopulationseeding as initpopseeding
import pynguin.configuration as config
import pynguin.ga.testcasefactory as tcf
import pynguin.generator as gen
import pynguin.testcase.defaulttestcase as dtc
from pynguin.generation.generationalgorithmfactory import TestSuiteGenerationAlgorithmFactory
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
        "seedmodules"
    )
    return dummy_test_file


@pytest.fixture()
def init_pop_seeding_instance():
    initpopseeding.initialpopulationseeding = initpopseeding.InitialPopulationSeeding()
    return initpopseeding.initialpopulationseeding


@pytest.fixture()
def triangle_test_cluster() -> TestCluster:
    test_cluster = TestClusterGenerator("tests.fixtures.examples.triangle").generate_cluster()
    return test_cluster


@pytest.fixture()
def dummy_test_cluster() -> TestCluster:
    test_cluster = TestClusterGenerator("tests.fixtures.seeding.initialpopulationseeding.dummycontainer") \
        .generate_cluster()
    return test_cluster


def test_get_testcases(init_pop_seeding_instance, seed_modules_path, triangle_test_cluster):
    init_pop_seeding_instance.test_cluster = triangle_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "triangleseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    assert init_pop_seeding_instance.has_tests
    assert len(init_pop_seeding_instance._testcases) == 2


def test_get_seeded_testcase(init_pop_seeding_instance, seed_modules_path, triangle_test_cluster):
    init_pop_seeding_instance.test_cluster = triangle_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "triangleseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert type(seeded_testcase) is dtc.DefaultTestCase


def test_assign_positive_floats(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "floatseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert next(iter(seeded_testcase.statements[2].assertions)).value == "Floats are different!"


def test_assign_negative_floats(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "negativefloatseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert next(iter(seeded_testcase.statements[2].assertions)).value == "Floats are equal!"


def test_assign_bools(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "boolseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert next(iter(seeded_testcase.statements[2].assertions)).value == "Bools are equal!"


def test_assign_negated_bools(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "negatedboolseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert next(iter(seeded_testcase.statements[2].assertions)).value == "Bools are different!"


def test_assign_none(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "noneseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert next(iter(seeded_testcase.statements[1].assertions)).value == "Is None!"


def test_assign_no_primitive_value(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "noprimitiveseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert len(seeded_testcase.statements) == 0


def test_assign_string(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "stringseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert next(iter(seeded_testcase.statements[2].assertions)).value == "Strings are different!"


def test_assign_function_wrong_name(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "wrongfunctionnameseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert seeded_testcase is not None
    assert len(seeded_testcase.statements) == 0


def test_generator_with_init_pop_seeding(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    config.configuration.initial_population_seeding = True
    config.configuration.initial_population_data = os.path.join(seed_modules_path, "boolseed.py")
    generator = gen.Pynguin(config.configuration)
    generator._setup_initial_population_seeding(dummy_test_cluster)
    seeded_testcase = init_pop_seeding_instance.seeded_testcase
    assert init_pop_seeding_instance.has_tests
    assert next(iter(seeded_testcase.statements[2].assertions)).value == "Bools are equal!"


def test_seeded_test_case_factory_no_delegation(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "boolseed.py")
    config.configuration.initial_population_seeding = True
    config.configuration.initial_population_data = init_pop_file
    config.configuration.seeded_testcases_reuse_probability = 1.0
    init_pop_seeding_instance.collect_testcases(init_pop_file)
    test_factory = TestFactory(dummy_test_cluster)
    delegate = tcf.RandomLengthTestCaseFactory(test_factory)
    test_case_factory = tcf.SeededTestCaseFactory(delegate, test_factory)

    seeded_testcase = test_case_factory.get_test_case()
    assert next(iter(seeded_testcase.statements[2].assertions)).value == "Bools are equal!"


def test_seeded_test_case_factory_with_delegation(init_pop_seeding_instance, seed_modules_path, dummy_test_cluster):
    init_pop_seeding_instance.test_cluster = dummy_test_cluster
    init_pop_file = os.path.join(seed_modules_path, "boolseed.py")
    config.configuration.initial_population_seeding = True
    config.configuration.initial_population_data = init_pop_file
    config.configuration.seeded_testcases_reuse_probability = 0.0
    init_pop_seeding_instance.collect_testcases(init_pop_file)
    test_factory = TestFactory(dummy_test_cluster)
    delegate = tcf.RandomLengthTestCaseFactory(test_factory)
    delegate.get_test_case = MagicMock()
    test_case_factory = tcf.SeededTestCaseFactory(delegate, test_factory)
    test_case_factory.get_test_case()
    delegate.get_test_case.assert_called_once()


@mock.patch("pynguin.testcase.execution.testcaseexecutor.TestCaseExecutor")
def test_algorithm_generation_factory_with_init_pop_seeding(
        mock_class,
        dummy_test_cluster):
    config.configuration.initial_population_seeding = True
    tsfactory = TestSuiteGenerationAlgorithmFactory(mock_class.return_value , dummy_test_cluster)
    chromosome_factory = tsfactory._get_chromosome_factory()
    test_case_factory = chromosome_factory.test_case_chromosome_factory._test_case_factory
    assert type(test_case_factory) == tcf.SeededTestCaseFactory


@mock.patch("pynguin.testcase.execution.testcaseexecutor.TestCaseExecutor")
def test_algorithm_generation_factory_without_init_pop_seeding(
        mock_class,
        dummy_test_cluster):
    config.configuration.initial_population_seeding = False
    tsfactory = TestSuiteGenerationAlgorithmFactory(mock_class.return_value, dummy_test_cluster)
    chromosome_factory = tsfactory._get_chromosome_factory()
    test_case_factory = chromosome_factory.test_case_chromosome_factory._test_case_factory
    assert type(test_case_factory) == tcf.RandomLengthTestCaseFactory
