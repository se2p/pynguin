import os

import pytest
import pynguin.analyses.seeding.initialpopulationseeding as initpopseeding
from pynguin.setup.testcluster import TestCluster
from pynguin.setup.testclustergenerator import TestClusterGenerator
from tests.fixtures.seeding.initialpopulationseeding import triangleseed


@pytest.fixture()
def init_pop_path():
    dummy_test_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "fixtures",
        "seeding",
        "initialpopulationseeding"
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


def test_get_testcase(init_pop_seeding_instance, init_pop_path, triangle_test_cluster):
    init_pop_seeding_instance._test_cluster = triangle_test_cluster
    init_pop_file = os.path.join(init_pop_path, "triangleseed.py")
    init_pop_seeding_instance.collect_testcases(init_pop_file)

    assert init_pop_seeding_instance.has_tests
    assert len(init_pop_seeding_instance._testcases) == 2
