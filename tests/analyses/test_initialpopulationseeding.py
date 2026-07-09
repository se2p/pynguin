#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import operator
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasefactory as tcf
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
from pynguin.analyses import seeding
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import ModuleTestCluster, generate_test_cluster
from pynguin.ga.generationalgorithmfactory import TestSuiteGenerationAlgorithmFactory

SEED_MODULES_PATH = (
    Path(__file__).parent
    / ".."
    / "fixtures"
    / "seeding"
    / "initialpopulationseeding"
    / "seedmodules"
)
DUMMY_MODULE_NAME = "tests.fixtures.seeding.initialpopulationseeding.dummycontainer"
TRIANGLE_MODULE_NAME = "tests.fixtures.examples.triangle"


@pytest.fixture
def seed_modules_path():
    return SEED_MODULES_PATH


@pytest.fixture
def triangle_test_cluster() -> ModuleTestCluster:
    return generate_test_cluster(TRIANGLE_MODULE_NAME)


@pytest.fixture
def dummy_test_cluster() -> ModuleTestCluster:
    return generate_test_cluster(DUMMY_MODULE_NAME)


@pytest.fixture
def constant_provider():
    return EmptyConstantProvider()


def _dummy_seed_dir(tmp_path: Path, fixture_name: str) -> Path:
    """Copy a dummycontainer-based fixture into a fresh directory.

    File discovery (``InitialPopulationProvider._read_module_source``) matches
    files by the *last dotted component* of ``config.configuration.module_name``.
    SUT-alias normalization, on the other hand, needs ``module_name`` to equal
    the actual dotted import path used inside the file. The seed fixtures were
    written for an AST-based transformer that never checked either of those, so
    they use scenario-keyword filenames (``primitiveseed_test_.py``, ...) with a
    shared ``dummycontainer`` import; copying the fixture into a fresh directory
    under a ``dummycontainer_test_*.py``-style name lets both mechanisms agree
    on ``config.configuration.module_name = DUMMY_MODULE_NAME``.
    """
    content = (SEED_MODULES_PATH / fixture_name).read_text(encoding="utf-8")
    dest = tmp_path / "dummycontainer_test_seed.py"
    dest.write_text(content, encoding="utf-8")
    return tmp_path


def test_get_testcases(constant_provider, seed_modules_path, triangle_test_cluster):
    config.configuration.module_name = TRIANGLE_MODULE_NAME
    provider = seeding.InitialPopulationProvider(
        triangle_test_cluster,
        tf.TestFactory(triangle_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)

    assert len(provider) == 2


def test_get_seeded_testcase(constant_provider, seed_modules_path, triangle_test_cluster):
    config.configuration.module_name = TRIANGLE_MODULE_NAME
    provider = seeding.InitialPopulationProvider(
        triangle_test_cluster,
        tf.TestFactory(triangle_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)

    seeded_testcase = provider.random_testcase()
    assert isinstance(seeded_testcase, tc.TestCase)


@mock.patch("pynguin.utils.randomness.choice")
def test_get_seeded_testcase_content(
    rand_mock, constant_provider, seed_modules_path, triangle_test_cluster
):
    config.configuration.module_name = TRIANGLE_MODULE_NAME
    provider = seeding.InitialPopulationProvider(
        triangle_test_cluster,
        tf.TestFactory(triangle_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_modules_path)
    rand_mock.side_effect = operator.itemgetter(0)

    seeded_testcase = provider.random_testcase()
    assert "triangle_.triangle(" in seeded_testcase.to_code()
    call_stmt = seeded_testcase.statements()[-1]
    assert call_stmt.assertions[0].object == "Isosceles triangle"


@pytest.mark.parametrize(
    "fixture_name, position, result, testcase_pos",
    [
        pytest.param("primitiveseed_test_.py", 2, "Floats are different!", 0),
        pytest.param("primitiveseed_test_.py", 2, "Floats are equal!", 1),
        pytest.param("primitiveseed_test_.py", 2, "Bools are equal!", 2),
        pytest.param("primitiveseed_test_.py", 2, "Bools are different!", 3),
        pytest.param("primitiveseed_test_.py", 1, "Is None!", 4),
        pytest.param("primitiveseed_test_.py", 2, "Strings are different!", 5),
        pytest.param("primitiveseed_test_.py", 2, "Bytes are different!", 6),
        pytest.param("collseed_test_.py", 1, "not empty!", 0),
        pytest.param("collseed_test_.py", 1, "not empty!", 1),
        pytest.param("collfuncseed_test_.py", 1, "empty!", 0),
        pytest.param("collfuncseed_test_.py", 1, "empty!", 1),
        pytest.param("collfuncseed_test_.py", 1, "not empty!", 2),
        pytest.param("nestedseed_test_.py", 2, "not empty!", 0),
        pytest.param("classseed_test_.py", 3, "not empty!", 0),
    ],
)
@mock.patch("pynguin.utils.randomness.choice")
def test_collect_different_types(  # noqa: PLR0917
    rand_mock,
    constant_provider,
    tmp_path,
    dummy_test_cluster,
    fixture_name,
    result,
    position,
    testcase_pos,
):
    config.configuration.module_name = DUMMY_MODULE_NAME
    seed_dir = _dummy_seed_dir(tmp_path, fixture_name)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster,
        tf.TestFactory(dummy_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_dir)
    rand_mock.side_effect = operator.itemgetter(testcase_pos)

    seeded_testcase = provider.random_testcase()
    assert seeded_testcase is not None
    assert seeded_testcase.get_statement(position).assertions[0].object == result


def test_create_assertion(constant_provider, tmp_path, dummy_test_cluster):
    config.configuration.module_name = DUMMY_MODULE_NAME
    seed_dir = _dummy_seed_dir(tmp_path, "assertseed_test_.py")
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster,
        tf.TestFactory(dummy_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_dir)

    # test_case1: a lone `var0 = -1; assert var0 == -1` -> ObjectAssertion(-1)
    with_assertion = next(
        t for t in provider._testcases if t.size() == 1 and t.get_statement(0).assertions
    )
    assert len(with_assertion.get_statement(0).assertions) == 1
    assert with_assertion.get_statement(0).assertions[0].object == -1


@pytest.mark.parametrize(
    "fixture_name, expected_len",
    [
        pytest.param("notprimseed_test_.py", 0),
        pytest.param("wrongfunctionnameseed_test_.py", 1),
        pytest.param("notknowncall_test_.py", 1),
        pytest.param("wrongassignseed_test_.py", 1),
    ],
)
def test_not_working_cases(
    constant_provider, tmp_path, dummy_test_cluster, fixture_name, expected_len
):
    """These fixtures exercise constructs discarded entirely by ``main``'s parser.

    ``main``'s all-or-nothing AST transformer discarded a whole test case on the
    first unparsable construct. The libcst-based parser is more lenient: a
    function contributes a (possibly partial) test case as long as at least one
    of its statements is admissible, so ``wrongfunctionnameseed``/
    ``notknowncall``/``wrongassignseed`` now seed a (partially uninterpreted)
    test case instead of nothing; only ``notprimseed`` (referencing a type that
    is neither a known variable nor resolvable against the test cluster) still
    yields zero test cases.
    """
    config.configuration.module_name = DUMMY_MODULE_NAME
    seed_dir = _dummy_seed_dir(tmp_path, fixture_name)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster,
        tf.TestFactory(dummy_test_cluster, constant_provider),
        constant_provider,
    )
    provider.collect_testcases(seed_dir)

    assert len(provider) == expected_len


@mock.patch("pynguin.utils.randomness.choice")
def test_seeded_test_case_factory_no_delegation(
    rand_mock, constant_provider, tmp_path, dummy_test_cluster
):
    rand_mock.side_effect = operator.itemgetter(2)
    test_factory = tf.TestFactory(dummy_test_cluster, constant_provider)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster, test_factory, constant_provider
    )
    config.configuration.module_name = DUMMY_MODULE_NAME
    seed_dir = _dummy_seed_dir(tmp_path, "primitiveseed_test_.py")
    config.configuration.seeding.initial_population_seeding = True
    config.configuration.seeding.initial_population_data = seed_dir
    config.configuration.seeding.seeded_testcases_reuse_probability = 1.0
    provider.collect_testcases(seed_dir)
    delegate = tcf.RandomLengthTestCaseFactory(test_factory, dummy_test_cluster)
    test_case_factory = tcf.SeededTestCaseFactory(delegate, provider)

    seeded_testcase = test_case_factory.get_test_case()
    assert seeded_testcase.get_statement(2).assertions[0].object == "Bools are equal!"


@mock.patch("pynguin.utils.randomness.choice")
def test_seeded_test_case_factory_with_delegation(
    rand_mock, constant_provider, tmp_path, dummy_test_cluster
):
    rand_mock.side_effect = operator.itemgetter(2)  # pragma: no cover
    test_factory = tf.TestFactory(dummy_test_cluster, constant_provider)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster, test_factory, constant_provider
    )
    config.configuration.module_name = DUMMY_MODULE_NAME
    seed_dir = _dummy_seed_dir(tmp_path, "primitiveseed_test_.py")
    config.configuration.seeding.initial_population_seeding = True
    config.configuration.seeding.initial_population_data = seed_dir
    config.configuration.seeding.seeded_testcases_reuse_probability = 0.0
    provider.collect_testcases(seed_dir)
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


@mock.patch("pynguin.ga.testcasechromosome.TestCaseChromosome.mutate")
def test_initial_mutation(mutate_mock, constant_provider, tmp_path, dummy_test_cluster):
    config.configuration.seeding.initial_population_mutations = 2
    config.configuration.module_name = DUMMY_MODULE_NAME
    seed_dir = _dummy_seed_dir(tmp_path, "primitiveseed_test_.py")
    test_factory = tf.TestFactory(dummy_test_cluster, constant_provider)
    provider = seeding.InitialPopulationProvider(
        dummy_test_cluster, test_factory, constant_provider
    )
    provider.collect_testcases(seed_dir)
    mutate_mock.assert_called()
