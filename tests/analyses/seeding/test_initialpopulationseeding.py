import os

import pytest

import pynguin.analyses.seeding.initialpopulationseeding as initpopseeding
import pynguin.testcase.defaulttestcase as dtc
from pynguin.setup.testcluster import TestCluster
from pynguin.setup.testclustergenerator import TestClusterGenerator


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

