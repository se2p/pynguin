#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Pynguin is an automated unit test generation framework for Python.

The framework generates unit tests for a given Python module.  For this it
supports various approaches, such as a random approach, similar to Randoop or a
whole-suite approach, based on a genetic algorithm, as implemented in EvoSuite.  The
framework allows to export test suites in various styles, i.e., using the `unittest`
library from the Python standard library or tests in the style used by the PyTest
framework.

Pynguin is supposed to be used as a standalone command-line application but it
can also be used as a library by instantiating this class directly.
"""
import enum
import importlib
import logging
import os
import sys
import threading
from typing import List, Optional, Tuple

import pynguin.analyses.seeding.initialpopulationseeding as initpopseeding
import pynguin.assertion.assertiongenerator as ag
import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.chromosomeconverter as cc
import pynguin.ga.postprocess as pp
import pynguin.generation.generationalgorithmfactory as gaf
import pynguin.testcase.testcase as tc
import pynguin.utils.statistics.statistics as stat
from pynguin.analyses.seeding.constantseeding import static_constant_seeding
from pynguin.ga.fitnessfunctions.fitness_utilities import compute_branch_coverage
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.export.exportprovider import ExportProvider
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.setup.testcluster import TestCluster
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable
from pynguin.utils.statistics.timer import Timer


@enum.unique
class ReturnCode(enum.IntEnum):
    """Return codes for Pynguin to signal result."""

    OK = 0
    """Symbolises that the execution ended as expected."""

    SETUP_FAILED = 1
    """Symbolises that the execution failed in the setup phase."""

    NO_TESTS_GENERATED = 2
    """Symbolises that no test could be generated."""


_LOGGER = logging.getLogger(__name__)


def set_configuration(configuration: config.Configuration) -> None:
    """Initialises the test generator with the given configuration.

    Args:
        configuration: The configuration to use.
    """
    config.configuration = configuration


def run_pynguin() -> ReturnCode:
    """Run the test generation.

    The result of the test generation is indicated by the resulting ReturnCode.

    Returns:
        See ReturnCode.

    Raises:
        ConfigurationException: In case the configuration is illegal
    """
    try:
        _LOGGER.info("Start Pynguin Test Generation…")
        return _run()
    finally:
        _LOGGER.info("Stop Pynguin Test Generation…")


def _setup_test_cluster() -> Optional[TestCluster]:
    with Timer(name="Test-cluster generation time", logger=None):
        test_cluster = TestClusterGenerator(
            config.configuration.module_name
        ).generate_cluster()
        if test_cluster.num_accessible_objects_under_test() == 0:
            _LOGGER.error("SUT contains nothing we can test.")
            return None
        return test_cluster


def _setup_path() -> bool:
    """Inserts the path to the SUT into the path list, installs the import hook and
    tries to load the SUT.

    Returns:
        An optional execution tracer, if loading was successful, None otherwise.
    """
    if not os.path.isdir(config.configuration.project_path):
        _LOGGER.error(
            "%s is not a valid project path", config.configuration.project_path
        )
        return False
    _LOGGER.debug("Setting up path for %s", config.configuration.project_path)
    sys.path.insert(0, config.configuration.project_path)
    return True


def _setup_import_hook() -> ExecutionTracer:
    _LOGGER.debug("Setting up instrumentation for %s", config.configuration.module_name)
    tracer = ExecutionTracer()
    install_import_hook(config.configuration.module_name, tracer)
    return tracer


def _load_sut(tracer: ExecutionTracer) -> bool:
    try:
        # We need to set the current thread ident so the import trace is recorded.
        tracer.current_thread_ident = threading.currentThread().ident
        importlib.import_module(config.configuration.module_name)
    except ImportError as ex:
        # A module could not be imported because some dependencies
        # are missing or it is malformed
        _LOGGER.exception("Failed to load SUT: %s", ex)
        return False
    return True


def _setup_random_number_generator() -> None:
    """Setup RNG."""
    if config.configuration.seeding.seed is None:
        _LOGGER.info("No seed given. Using %d", randomness.RNG.get_seed())
    else:
        _LOGGER.info("Using seed %d", config.configuration.seeding.seed)
        randomness.RNG.seed(config.configuration.seeding.seed)


def _setup_constant_seeding_collection() -> None:
    """Collect constants from SUT, if enabled."""
    if config.configuration.seeding.constant_seeding:
        _LOGGER.info("Collecting constants from SUT.")
        static_constant_seeding.collect_constants(config.configuration.project_path)


def _setup_initial_population_seeding(test_cluster: TestCluster):
    """Collect and parse tests for seeding the initial population"""
    if config.configuration.seeding.initial_population_seeding:
        _LOGGER.info("Collecting and parsing provided testcases.")
        initpopseeding.initialpopulationseeding.test_cluster = test_cluster
        initpopseeding.initialpopulationseeding.collect_testcases(
            config.configuration.seeding.initial_population_data
        )


def _setup_and_check() -> Optional[Tuple[TestCaseExecutor, TestCluster]]:
    """Load the System Under Test (SUT) i.e. the module that is tested.

    Perform setup and some sanity checks.

    Returns:
        An optional tuple of test-case executor and test cluster
    """

    if not _setup_path():
        return None
    tracer = _setup_import_hook()
    if not _load_sut(tracer):
        return None

    # Analyzing the SUT should not cause any coverage.
    tracer.disable()
    if (test_cluster := _setup_test_cluster()) is None:
        return None
    tracer.enable()

    executor = TestCaseExecutor(tracer)
    _track_sut_data(tracer, test_cluster)
    _setup_random_number_generator()
    _setup_constant_seeding_collection()
    _setup_initial_population_seeding(test_cluster)
    return executor, test_cluster


def _track_sut_data(tracer: ExecutionTracer, test_cluster: TestCluster) -> None:
    """Track data from the SUT.

    Args:
        tracer: the execution tracer
        test_cluster: the test cluster
    """
    stat.track_output_variable(
        RuntimeVariable.CodeObjects,
        len(tracer.get_known_data().existing_code_objects),
    )
    stat.track_output_variable(
        RuntimeVariable.Predicates,
        len(tracer.get_known_data().existing_predicates),
    )
    stat.track_output_variable(
        RuntimeVariable.AccessibleObjectsUnderTest,
        test_cluster.num_accessible_objects_under_test(),
    )
    stat.track_output_variable(
        RuntimeVariable.GeneratableTypes,
        len(test_cluster.get_all_generatable_types()),
    )
    # TODO(fk) make this work for other criteria beyond branch coverage.
    stat.track_output_variable(
        RuntimeVariable.ImportBranchCoverage,
        compute_branch_coverage(tracer.import_trace, tracer.get_known_data()),
    )


def _run() -> ReturnCode:
    if (setup_result := _setup_and_check()) is None:
        return ReturnCode.SETUP_FAILED
    executor, test_cluster = setup_result

    with Timer(name="Test generation time", logger=None):
        algorithm: TestGenerationStrategy = _instantiate_test_generation_strategy(
            executor, test_cluster
        )
        _LOGGER.info("Start generating test cases")
        generation_result = algorithm.generate_tests()
        if algorithm.stopping_condition.is_fulfilled():
            _LOGGER.info("Used up all resources (%s).", algorithm.stopping_condition)
        _LOGGER.info("Stop generating test cases")

        with Timer(name="Re-execution time", logger=None):
            stat.track_output_variable(
                RuntimeVariable.Coverage, generation_result.get_coverage()
            )

        if config.configuration.test_case_output.post_process:
            truncation = pp.ExceptionTruncation()
            generation_result.accept(truncation)

            unused_primitives_removal = pp.TestCasePostProcessor(
                [pp.UnusedStatementsTestCaseVisitor()]
            )
            generation_result.accept(unused_primitives_removal)
            # TODO(fk) add more postprocessing stuff.

        if config.configuration.test_case_output.generate_assertions:
            generator = ag.AssertionGenerator(executor)
            generation_result.accept(generator)

        with Timer(name="Export time", logger=None):
            converter = cc.ChromosomeConverter()
            generation_result.accept(converter)
            failing = converter.failing_test_suite
            passing = converter.passing_test_suite
            written_to = _export_test_cases(
                [t.test_case for t in passing.test_case_chromosomes]
            )
            _LOGGER.info(
                "Export %i successful test cases to %s",
                passing.size(),
                written_to,
            )
            written_to = _export_test_cases(
                [t.test_case for t in failing.test_case_chromosomes],
                "_failing",
                wrap_code=True,
            )
            _LOGGER.info(
                "Export %i failing test cases to %s", failing.size(), written_to
            )

    _track_statistics(passing, failing, generation_result)
    _collect_statistics()
    if not stat.write_statistics():
        _LOGGER.error("Failed to write statistics data")
    if generation_result.size() == 0:
        # not able to generate one test case
        return ReturnCode.NO_TESTS_GENERATED
    return ReturnCode.OK


def _instantiate_test_generation_strategy(
    executor: TestCaseExecutor, test_cluster: TestCluster
) -> TestGenerationStrategy:
    factory = gaf.TestSuiteGenerationAlgorithmFactory(executor, test_cluster)
    return factory.get_search_algorithm()


def _collect_statistics() -> None:
    stat.track_output_variable(
        RuntimeVariable.TargetModule, config.configuration.module_name
    )
    stat.track_output_variable(RuntimeVariable.RandomSeed, randomness.RNG.get_seed())
    stat.track_output_variable(
        RuntimeVariable.ConfigurationId,
        config.configuration.statistics_output.configuration_id,
    )
    stat.track_output_variable(
        RuntimeVariable.ProjectName, config.configuration.statistics_output.project_name
    )
    for runtime_variable, value in stat.variables_generator:
        stat.set_output_variable_for_runtime_variable(runtime_variable, value)


def _track_statistics(
    passing: chrom.Chromosome,
    failing: chrom.Chromosome,
    result: chrom.Chromosome,
) -> None:
    stat.current_individual(result)
    stat.track_output_variable(RuntimeVariable.Size, result.size())
    stat.track_output_variable(RuntimeVariable.Length, result.length())
    stat.track_output_variable(RuntimeVariable.FailingSize, failing.size())
    stat.track_output_variable(
        RuntimeVariable.FailingLength,
        failing.length(),
    )
    stat.track_output_variable(RuntimeVariable.PassingSize, passing.size())
    stat.track_output_variable(RuntimeVariable.PassingLength, passing.length())


def _export_test_cases(
    test_cases: List[tc.TestCase], suffix: str = "", wrap_code: bool = False
) -> str:
    """Export the given test cases.

    Args:
        test_cases: A list of test cases to export
        suffix: Suffix that can be added to the file name to distinguish
            between different results e.g., failing and succeeding test cases.
        wrap_code: Whether or not the generated code shall be wrapped

    Returns:
        The name of the target file
    """
    exporter = ExportProvider.get_exporter(wrap_code=wrap_code)
    target_file = os.path.join(
        config.configuration.test_case_output.output_path,
        "test_" + config.configuration.module_name.replace(".", "_") + suffix + ".py",
    )
    exporter.export_sequences(target_file, test_cases)
    return target_file
