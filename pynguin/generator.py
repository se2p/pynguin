#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
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
from __future__ import annotations

import datetime
import enum
import importlib
import logging
import os
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import pynguin.assertion.assertiongenerator as ag
import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.computations as ff
import pynguin.ga.postprocess as pp
import pynguin.ga.testsuitechromosome as tsc
import pynguin.generation.generationalgorithmfactory as gaf
import pynguin.utils.statistics.statistics as stat
from pynguin.analyses.constants import (
    ConstantPool,
    ConstantProvider,
    DelegatingConstantProvider,
    DynamicConstantProvider,
    EmptyConstantProvider,
    collect_static_constants,
)
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.types import TypeInferenceStrategy
from pynguin.generation import export
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import (
    ExecutionTracer,
    ReturnTypeObserver,
    TestCaseExecutor,
)
from pynguin.utils import randomness
from pynguin.utils.report import get_coverage_report, render_coverage_report
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.generation.algorithms.testgenerationstrategy import (
        TestGenerationStrategy,
    )


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


def _setup_test_cluster() -> ModuleTestCluster | None:
    # TODO this is ugly and needs to be reworked...
    match config.configuration.type_inference:
        case config.TypeInferenceStrategy.TYPE_HINTS:
            strategy = TypeInferenceStrategy.TYPE_HINTS
        case config.TypeInferenceStrategy.NONE:
            strategy = TypeInferenceStrategy.NONE
        case _:
            strategy = TypeInferenceStrategy.TYPE_HINTS
    test_cluster = generate_test_cluster(config.configuration.module_name, strategy)
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


def _setup_import_hook(
    dynamic_constant_provider: DynamicConstantProvider | None,
) -> ExecutionTracer:
    _LOGGER.debug("Setting up instrumentation for %s", config.configuration.module_name)
    tracer = ExecutionTracer()

    install_import_hook(
        config.configuration.module_name,
        tracer,
        dynamic_constant_provider=dynamic_constant_provider,
    )
    return tracer


def _load_sut(tracer: ExecutionTracer) -> bool:
    try:
        # We need to set the current thread ident so the import trace is recorded.
        tracer.current_thread_identifier = threading.current_thread().ident
        importlib.import_module(config.configuration.module_name)
    except ImportError as ex:
        # A module could not be imported because some dependencies
        # are missing or it is malformed
        _LOGGER.exception("Failed to load SUT: %s", ex)
        return False
    return True


def _setup_report_dir() -> bool:
    # Report dir only needs to be created when statistics or coverage report is enabled.
    if (
        config.configuration.statistics_output.statistics_backend
        != config.StatisticsBackend.NONE
        or config.configuration.statistics_output.create_coverage_report
    ):
        report_dir = Path(config.configuration.statistics_output.report_dir).absolute()
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, FileNotFoundError):
            _LOGGER.error(
                "Cannot create report dir %s",
                config.configuration.statistics_output.report_dir,
                exc_info=True,
            )
            return False
    return True


def _setup_random_number_generator() -> None:
    """Setup RNG."""
    _LOGGER.info("Using seed %d", config.configuration.seeding.seed)
    randomness.RNG.seed(config.configuration.seeding.seed)


def _setup_constant_seeding() -> tuple[
    ConstantProvider, DynamicConstantProvider | None
]:
    """Collect constants from SUT, if enabled."""
    # Use empty provider by default.
    wrapped_provider: ConstantProvider = EmptyConstantProvider()
    # We need to return the provider used for dynamic values separately,
    # because it is later on used to hook up the instrumentation calls.
    dynamic_constant_provider: DynamicConstantProvider | None = None
    if config.configuration.seeding.constant_seeding:
        _LOGGER.info("Collecting static constants from module under test")
        constant_pool = collect_static_constants(config.configuration.project_path)
        if len(constant_pool) == 0:
            _LOGGER.info("No constants found")
        else:
            _LOGGER.info("Constants found: %s", len(constant_pool))
            # Probability of 1.0 -> if a value is requested and available -> return it.
            wrapped_provider = DelegatingConstantProvider(
                constant_pool, wrapped_provider, 1.0
            )

    if config.configuration.seeding.dynamic_constant_seeding:
        _LOGGER.info("Setting up runtime collection of constants")
        dynamic_constant_provider = DynamicConstantProvider(
            ConstantPool(),
            wrapped_provider,
            config.configuration.seeding.seeded_dynamic_values_reuse_probability,
        )
        wrapped_provider = dynamic_constant_provider

    return wrapped_provider, dynamic_constant_provider


def _setup_and_check() -> tuple[
    TestCaseExecutor, ModuleTestCluster, ConstantProvider
] | None:
    """Load the System Under Test (SUT) i.e. the module that is tested.

    Perform setup and some sanity checks.

    Returns:
        An optional tuple of test-case executor and test cluster
    """

    if not _setup_path():
        return None
    wrapped_constant_provider, dynamic_constant_provider = _setup_constant_seeding()
    tracer = _setup_import_hook(dynamic_constant_provider)
    if not _load_sut(tracer):
        return None
    if not _setup_report_dir():
        return None

    # Analyzing the SUT should not cause any coverage.
    tracer.disable()
    if (test_cluster := _setup_test_cluster()) is None:
        return None
    tracer.enable()

    executor = TestCaseExecutor(tracer)
    _track_sut_data(tracer, test_cluster)
    _setup_random_number_generator()
    return executor, test_cluster, wrapped_constant_provider


def _track_sut_data(tracer: ExecutionTracer, test_cluster: ModuleTestCluster) -> None:
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
        RuntimeVariable.Lines,
        len(tracer.get_known_data().existing_lines),
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
        ff.compute_branch_coverage(tracer.import_trace, tracer.get_known_data()),
    )
    stat.track_output_variable(
        RuntimeVariable.ImportLineCoverage,
        ff.compute_line_coverage(tracer.import_trace, tracer.get_known_data()),
    )


def _get_coverage_ff_from_algorithm(
    algorithm: TestGenerationStrategy, function_type: type[ff.CoverageFunction]
) -> ff.CoverageFunction:
    """Retrieve the coverage function for a test suite of a given coverage type.

    Args:
        algorithm: The test generation strategy
        function_type: the type of coverage function to receive

    Returns:
        The coverage function for a test suite for this run of the given type
    """
    test_suite_coverage_func = None
    for coverage_func in algorithm.test_suite_coverage_functions:
        if isinstance(coverage_func, function_type):
            test_suite_coverage_func = coverage_func
    assert (
        test_suite_coverage_func
    ), "The required coverage function was not initialised"
    return test_suite_coverage_func


def _run() -> ReturnCode:
    if (setup_result := _setup_and_check()) is None:
        return ReturnCode.SETUP_FAILED
    executor, test_cluster, constant_provider = setup_result
    # Observe return types during execution.
    executor.add_observer(ReturnTypeObserver())

    algorithm: TestGenerationStrategy = _instantiate_test_generation_strategy(
        executor, test_cluster, constant_provider
    )
    _LOGGER.info("Start generating test cases")
    generation_result = algorithm.generate_tests()
    if algorithm.resources_left():
        _LOGGER.info("Algorithm stopped before using all resources.")
    else:
        _LOGGER.info("Stopping condition reached")
        for stop in algorithm.stopping_conditions:
            _LOGGER.info("%s", stop)
    _LOGGER.info("Stop generating test cases")

    # Executions that happen after this point should not influence the
    # search statistics
    executor.clear_observers()

    _track_coverage_metrics(algorithm, generation_result)

    # Remove statements after exceptions
    truncation = pp.ExceptionTruncation()
    generation_result.accept(truncation)
    if config.configuration.test_case_output.post_process:

        unused_primitives_removal = pp.TestCasePostProcessor(
            [pp.UnusedStatementsTestCaseVisitor()]
        )
        generation_result.accept(unused_primitives_removal)
        # TODO(fk) add more postprocessing stuff.

    ass_gen = config.configuration.test_case_output.assertion_generation
    if ass_gen != config.AssertionGenerator.NONE:
        _LOGGER.info("Start generating assertions")
        if ass_gen == config.AssertionGenerator.MUTATION_ANALYSIS:
            generator: cv.ChromosomeVisitor = ag.MutationAnalysisAssertionGenerator(
                executor
            )
        else:
            generator = ag.AssertionGenerator(executor)
        generation_result.accept(generator)

    # Export the generated test suites
    if (
        config.configuration.test_case_output.export_strategy
        == config.ExportStrategy.PY_TEST
    ):
        _export_chromosome(generation_result)

    if config.configuration.statistics_output.create_coverage_report:
        render_coverage_report(
            get_coverage_report(
                generation_result,
                executor,
                config.configuration.statistics_output.coverage_metrics,
            ),
            Path(config.configuration.statistics_output.report_dir) / "cov_report.html",
            datetime.datetime.now(),
        )
    _track_statistics(generation_result)
    _collect_statistics()
    if not stat.write_statistics():
        _LOGGER.error("Failed to write statistics data")
    if generation_result.size() == 0:
        # not able to generate one test case
        return ReturnCode.NO_TESTS_GENERATED
    return ReturnCode.OK


def _track_coverage_metrics(
    algorithm: TestGenerationStrategy, generation_result: tsc.TestSuiteChromosome
) -> None:
    """Track multiple set coverage metrics of the generated test suites.
    This possibly re-executes the test suites.

    Args:
        algorithm: The test generation strategy
        generation_result:  The resulting chromosome of the generation strategy
    """

    stat.track_output_variable(
        RuntimeVariable.Coverage, generation_result.get_coverage()
    )
    coverage_metrics = config.configuration.statistics_output.coverage_metrics
    if config.CoverageMetric.LINE in coverage_metrics:
        line_coverage_ff: ff.CoverageFunction = _get_coverage_ff_from_algorithm(
            algorithm, ff.TestSuiteLineCoverageFunction
        )
        stat.track_output_variable(
            RuntimeVariable.LineCoverage,
            generation_result.get_coverage_for(line_coverage_ff),
        )
    if config.CoverageMetric.BRANCH in coverage_metrics:
        branch_coverage_ff: ff.CoverageFunction = _get_coverage_ff_from_algorithm(
            algorithm, ff.TestSuiteBranchCoverageFunction
        )
        stat.track_output_variable(
            RuntimeVariable.BranchCoverage,
            generation_result.get_coverage_for(branch_coverage_ff),
        )


def _instantiate_test_generation_strategy(
    executor: TestCaseExecutor,
    test_cluster: ModuleTestCluster,
    constant_provider: ConstantProvider,
) -> TestGenerationStrategy:
    factory = gaf.TestSuiteGenerationAlgorithmFactory(
        executor, test_cluster, constant_provider
    )
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


def _track_statistics(result: chrom.Chromosome) -> None:
    stat.current_individual(result)
    stat.track_output_variable(RuntimeVariable.Size, result.size())
    stat.track_output_variable(RuntimeVariable.Length, result.length())


def _export_chromosome(
    chromosome: chrom.Chromosome,
    file_name_suffix: str = "",
) -> None:
    """Export the given chromosome.

    Args:
        chromosome: the chromosome to export.
        file_name_suffix: Suffix that can be added to the file name to distinguish
            between different results e.g., failing and succeeding test cases.
    Returns:
        The name of the target file
    """
    target_file = os.path.join(
        config.configuration.test_case_output.output_path,
        "test_"
        + config.configuration.module_name.replace(".", "_")
        + file_name_suffix
        + ".py",
    )
    export_visitor = export.PyTestChromosomeToAstVisitor()
    chromosome.accept(export_visitor)
    export.save_module_to_file(export_visitor.to_module(), target_file)
    _LOGGER.info("Written %i test cases to %s", chromosome.size(), target_file)
