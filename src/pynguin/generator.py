#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
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
import inspect
import json
import logging
import math
import sys
from pathlib import Path
from typing import TYPE_CHECKING, cast

try:
    import random

    from faker import Faker

    FANDANGO_FAKER_AVAILABLE = True
except ImportError:
    FANDANGO_FAKER_AVAILABLE = False

import pynguin.assertion.assertiongenerator as ag
import pynguin.assertion.llmassertiongenerator as lag
import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.assertion.mutation_analysis.strategies as ms
import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.computations as ff
import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.ga.postprocess as pp
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.stats as stat

if config.configuration.pynguinml.ml_testing_enabled or TYPE_CHECKING:
    import pynguin.utils.pynguinml.ml_testing_resources as tr

from pynguin.analyses.constants import (
    ConstantProvider,
    DelegatingConstantProvider,
    DynamicConstantProvider,
    EmptyConstantProvider,
    RestrictedConstantPool,
    collect_static_constants,
)
from pynguin.analyses.module import generate_test_cluster
from pynguin.assertion.mutation_analysis.controller import MutationController
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.instrumentation.machinery import InstrumentationFinder, install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.slicer.statementslicingobserver import RemoteStatementSlicingObserver
from pynguin.testcase import export
from pynguin.testcase.execution import (
    RemoteAssertionExecutionObserver,
    SubprocessTestCaseExecutor,
    TestCaseExecutor,
)
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConfigurationException, CoroutineFoundException
from pynguin.utils.llm import LLM, LLMProvider, extract_code
from pynguin.utils.report import (
    get_coverage_report,
    render_coverage_report,
    render_xml_coverage_report,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Callable

    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.assertion.mutation_analysis.operators.base import MutationOperator
    from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm

if config.configuration.pynguinml.ml_testing_enabled or TYPE_CHECKING:
    from pynguin.utils.pynguinml import np_rng


@enum.unique
class ReturnCode(enum.IntEnum):
    """Return codes for Pynguin to signal result."""

    OK = 0
    """Symbolises that the execution ended as expected."""

    SETUP_FAILED = 1
    """Symbolises that the execution failed in the setup phase."""

    NO_TESTS_GENERATED = 2
    """Symbolises that no test could be generated."""

    FINAL_METRICS_TRACKING_FAILED = 3
    """Symbolises that the final metrics tracking failed."""


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
        if config.configuration.algorithm == config.Algorithm.LLM:
            return _run_llm()
        return _run()
    finally:
        _LOGGER.info("Stop Pynguin Test Generation…")


def _setup_test_cluster() -> ModuleTestCluster | None:
    try:
        test_cluster = generate_test_cluster(
            config.configuration.module_name,
            config.configuration.type_inference.type_inference_strategy,
        )
    except ModuleNotFoundError as ex:
        _LOGGER.exception(
            """Module %s could not be found. This is likely due to a missing dependency.
            It may also be caused by a bug in the SUT, especially if it uses C-modules.
            """,
            ex.name,
        )
        return None
    except CoroutineFoundException as ex:
        _LOGGER.exception(
            "Pynguin does not support test generation for coroutines (async def): %s", ex
        )
        return None

    if test_cluster.num_accessible_objects_under_test() == 0:
        _LOGGER.error("SUT contains nothing we can test.")
        return None
    return test_cluster


def _setup_path() -> bool:
    """Set up the run-time path.

    Inserts the path to the SUT into the path list, installs the import hook and
    tries to load the SUT.

    Returns:
        An optional execution tracer, if loading was successful, None otherwise.
    """
    if not Path(config.configuration.project_path).is_dir():
        _LOGGER.error("%s is not a valid project path", config.configuration.project_path)
        return False
    _LOGGER.debug("Setting up path for %s", config.configuration.project_path)
    sys.path.insert(0, config.configuration.project_path)
    return True


def _setup_import_hook(
    dynamic_constant_provider: DynamicConstantProvider | None,
) -> SubjectProperties:
    _LOGGER.debug("Setting up instrumentation for %s", config.configuration.module_name)
    subject_properties = SubjectProperties()

    install_import_hook(
        config.configuration.module_name,
        subject_properties,
        dynamic_constant_provider=dynamic_constant_provider,
    )
    return subject_properties


def _load_sut(subject_properties: SubjectProperties) -> bool:
    module_name = config.configuration.module_name
    try:
        # We need to activate the tracer so the import trace is recorded.
        with subject_properties.instrumentation_tracer:
            # If the module is already imported, we need to reload it for the
            # ExecutionTracer to successfully register the subject_properties
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
    except Exception as ex:
        # A module could not be imported because some dependencies
        # are missing or it is malformed or any error is raised during the import
        _LOGGER.exception("Failed to load SUT: %s", ex)
        return False
    return True


def _setup_report_dir() -> bool:
    # Report dir only needs to be created when statistics or coverage report is enabled.
    if (
        config.configuration.statistics_output.statistics_backend != config.StatisticsBackend.NONE
        or config.configuration.statistics_output.create_coverage_report
    ):
        report_dir = Path(config.configuration.statistics_output.report_dir).absolute()
        try:
            report_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, FileNotFoundError):
            _LOGGER.exception(
                "Cannot create report dir %s",
                config.configuration.statistics_output.report_dir,
            )
            return False
    return True


def _setup_random_number_generator() -> None:
    """Setup RNG."""
    _LOGGER.info("Using seed %d", config.configuration.seeding.seed)
    randomness.RNG.seed(config.configuration.seeding.seed)
    if config.configuration.pynguinml.ml_testing_enabled:
        np_rng.init_rng(config.configuration.seeding.seed)

    if FANDANGO_FAKER_AVAILABLE:
        # Seed Fandango
        random.seed(config.configuration.seeding.seed)
        # Seed Faker
        Faker.seed(config.configuration.seeding.seed)


def _setup_constant_seeding() -> tuple[ConstantProvider, DynamicConstantProvider | None]:
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
            wrapped_provider = DelegatingConstantProvider(constant_pool, wrapped_provider, 1.0)

    if config.configuration.seeding.dynamic_constant_seeding:
        _LOGGER.info("Setting up runtime collection of constants")
        dynamic_constant_provider = DynamicConstantProvider(
            RestrictedConstantPool(max_size=config.configuration.seeding.max_dynamic_pool_size),
            wrapped_provider,
            config.configuration.seeding.seeded_dynamic_values_reuse_probability,
            config.configuration.seeding.max_dynamic_length,
        )
        wrapped_provider = dynamic_constant_provider

    return wrapped_provider, dynamic_constant_provider


def _setup_ml_testing_environment(test_cluster: ModuleTestCluster):
    # load resources once so they get cached
    tr.get_datatype_mapping()
    tr.get_nparray_function(test_cluster)
    tr.get_constructor_function(test_cluster)


def _verify_config() -> None:
    """Verify the configuration and raise an exception if something is invalid/not supported."""
    coverage_metrics = config.configuration.statistics_output.coverage_metrics
    if config.configuration.algorithm is config.configuration.algorithm.DYNAMOSA and any(
        m for m in coverage_metrics if m is not config.CoverageMetric.BRANCH
    ):
        raise ConfigurationException(
            "DynaMosa currently only supports branch coverage as coverage criterion."
        )


def _setup_and_check() -> tuple[TestCaseExecutor, ModuleTestCluster, ConstantProvider] | None:
    """Load the System Under Test (SUT) i.e. the module that is tested.

    Perform setup and some sanity checks.

    Returns:
        An optional tuple of test-case executor and test cluster
    """
    if not _setup_path():
        return None
    wrapped_constant_provider, dynamic_constant_provider = _setup_constant_seeding()
    subject_properties = _setup_import_hook(dynamic_constant_provider)
    if not _load_sut(subject_properties):
        return None
    if not _setup_report_dir():
        return None

    # Analyzing the SUT should not cause any coverage.
    subject_properties.instrumentation_tracer.disable()
    if (test_cluster := _setup_test_cluster()) is None:
        return None
    subject_properties.instrumentation_tracer.enable()

    # Make alias to make the following lines shorter...
    stop = config.configuration.stopping
    if config.configuration.subprocess:
        executor: TestCaseExecutor = SubprocessTestCaseExecutor(
            subject_properties=subject_properties,
            maximum_test_execution_timeout=stop.maximum_test_execution_timeout,
            test_execution_time_per_statement=stop.test_execution_time_per_statement,
        )
    else:
        executor = TestCaseExecutor(
            subject_properties=subject_properties,
            maximum_test_execution_timeout=stop.maximum_test_execution_timeout,
            test_execution_time_per_statement=stop.test_execution_time_per_statement,
        )
    _track_sut_data(subject_properties, test_cluster)
    _setup_random_number_generator()

    if config.configuration.pynguinml.ml_testing_enabled:
        _setup_ml_testing_environment(test_cluster)

    # Detect which LLM strategy is used
    stat.track_output_variable(RuntimeVariable.LLMStrategy, _detect_llm_strategy())
    return executor, test_cluster, wrapped_constant_provider


def _detect_llm_strategy() -> str:
    if config.configuration.large_language_model.hybrid_initial_population:
        return (
            f"Hybrid-Initial-Population-"
            f"{config.configuration.large_language_model.llm_test_case_percentage}"
        )
    if config.configuration.large_language_model.call_llm_on_stall_detection:
        return "LLM-On-Stall-Detection"
    if config.configuration.large_language_model.call_llm_for_uncovered_targets:
        return "LLM-For-Initial-Uncovered-Targets"
    if config.configuration.test_case_output.assertion_generation == config.AssertionGenerator.LLM:
        return "LLM-Assertion-Generator"
    return ""


def _track_sut_data(subject_properties: SubjectProperties, test_cluster: ModuleTestCluster) -> None:
    """Track data from the SUT.

    Args:
        subject_properties: The properties of the subject under test.
        test_cluster: the test cluster
    """
    stat.track_output_variable(
        RuntimeVariable.CodeObjects,
        len(subject_properties.existing_code_objects),
    )
    stat.track_output_variable(
        RuntimeVariable.Predicates,
        len(subject_properties.existing_predicates),
    )
    stat.track_output_variable(
        RuntimeVariable.Lines,
        len(subject_properties.existing_lines),
    )
    cyclomatic_complexities: list[int] = [
        code.cfg.cyclomatic_complexity for code in subject_properties.existing_code_objects.values()
    ]
    stat.track_output_variable(
        RuntimeVariable.McCabeCodeObject, json.dumps(cyclomatic_complexities)
    )
    test_cluster.track_statistics_values(stat.track_output_variable)
    if config.CoverageMetric.BRANCH in config.configuration.statistics_output.coverage_metrics:
        stat.track_output_variable(
            RuntimeVariable.ImportBranchCoverage,
            ff.compute_branch_coverage(
                subject_properties.instrumentation_tracer.import_trace,
                subject_properties,
            ),
        )
    if config.CoverageMetric.LINE in config.configuration.statistics_output.coverage_metrics:
        stat.track_output_variable(
            RuntimeVariable.ImportLineCoverage,
            ff.compute_line_coverage(
                subject_properties.instrumentation_tracer.import_trace,
                subject_properties,
            ),
        )


def _get_coverage_ff_from_algorithm(
    algorithm: GenerationAlgorithm, function_type: type[ff.TestSuiteCoverageFunction]
) -> ff.TestSuiteCoverageFunction:
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
    assert test_suite_coverage_func, "The required coverage function was not initialised"
    return test_suite_coverage_func


def _reload_instrumentation_loader(
    coverage_metrics: set[config.CoverageMetric],
    dynamic_constant_provider: DynamicConstantProvider | None,
    subject_properties: SubjectProperties,
):
    module_name = config.configuration.module_name
    module = importlib.import_module(module_name)
    first_finder: InstrumentationFinder | None = None
    for finder in sys.meta_path:
        if isinstance(finder, InstrumentationFinder):
            first_finder = finder
            break
    assert first_finder is not None
    first_finder.update_instrumentation_metrics(
        subject_properties=subject_properties,
        coverage_metrics=coverage_metrics,
        dynamic_constant_provider=dynamic_constant_provider,
    )
    try:
        with subject_properties.instrumentation_tracer:
            importlib.reload(module)
    except Exception as ex:
        _LOGGER.exception("Failed to reload SUT: %s", ex)
        return False
    return True


def _reset_cache_for_result(generation_result):
    generation_result.invalidate_cache()
    for test_case in generation_result.test_case_chromosomes:
        test_case.invalidate_cache()
        test_case.remove_last_execution_result()


def _track_final_metrics(
    algorithm,
    executor: TestCaseExecutor,
    generation_result: tsc.TestSuiteChromosome,
    constant_provider: ConstantProvider,
) -> set[config.CoverageMetric] | None:
    """Track the final coverage metrics.

    Re-loads all required instrumentations for metrics that were not already
    calculated and tracked during the result generation.
    These metrics are then also calculated on the result, which is executed
    once again with the new instrumentation.

    Args:
        algorithm: the used test-generation algorithm
        executor: the testcase executor of the run
        generation_result: the generated testsuite containing assertions
        constant_provider: the constant provider required for the
            reloading of the module

    Returns:
        The set of tracked coverage metrics, including the ones that we optimised for
        or None if the tracking failed.
    """
    output_variables = config.configuration.statistics_output.output_variables
    # Alias for shorter lines
    cov_metrics = config.configuration.statistics_output.coverage_metrics
    metrics_for_reinstrumenation: set[config.CoverageMetric] = set(cov_metrics)

    to_calculate: list[tuple[RuntimeVariable, ff.TestSuiteCoverageFunction]] = []

    add_additional_metrics(
        algorithm=algorithm,
        cov_metrics=cov_metrics,
        executor=executor,
        metrics_for_reinstrumentation=metrics_for_reinstrumenation,
        output_variables=output_variables,
        to_calculate=to_calculate,
    )

    # Assertion Checked Coverage is special...
    if RuntimeVariable.AssertionCheckedCoverage in output_variables:
        metrics_for_reinstrumenation.add(config.CoverageMetric.CHECKED)
        executor.set_instrument(True)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        assertion_checked_coverage_ff = ff.TestSuiteAssertionCheckedCoverageFunction(executor)
        to_calculate.append((
            RuntimeVariable.AssertionCheckedCoverage,
            assertion_checked_coverage_ff,
        ))

    # re-instrument the files
    dynamic_constant_provider = None
    if isinstance(constant_provider, DynamicConstantProvider):
        dynamic_constant_provider = constant_provider

    if not _reload_instrumentation_loader(
        metrics_for_reinstrumenation,
        dynamic_constant_provider,
        executor.subject_properties,
    ):
        return None

    # force new execution of the test cases after new instrumentation
    _reset_cache_for_result(generation_result)

    # set value for each newly calculated variable
    for runtime_variable, coverage_ff in to_calculate:
        generation_result.add_coverage_function(coverage_ff)
        _LOGGER.info(f"Calculating resulting {runtime_variable.value}")  # noqa: G004
        stat.track_output_variable(
            runtime_variable, generation_result.get_coverage_for(coverage_ff)
        )

    ass_gen = config.configuration.test_case_output.assertion_generation
    if (
        ass_gen == config.AssertionGenerator.CHECKED_MINIMIZING
        and RuntimeVariable.AssertionCheckedCoverage in output_variables
    ):
        _minimize_assertions(generation_result)

    # Collect other final stats on result
    stat.track_output_variable(RuntimeVariable.FinalLength, generation_result.length())
    stat.track_output_variable(RuntimeVariable.FinalSize, generation_result.size())

    # reset whether to instrument tests and assertions as well as the SUT
    instrument_test = config.CoverageMetric.CHECKED in cov_metrics
    executor.set_instrument(instrument_test)
    return metrics_for_reinstrumenation


def add_additional_metrics(  # noqa: D103
    *,
    algorithm,
    cov_metrics,
    executor,
    metrics_for_reinstrumentation,
    output_variables,
    to_calculate,
):
    if (
        RuntimeVariable.FinalLineCoverage in output_variables
        and config.CoverageMetric.LINE not in cov_metrics
    ):
        metrics_for_reinstrumentation.add(config.CoverageMetric.LINE)
        line_cov_ff = ff.TestSuiteLineCoverageFunction(executor)
        to_calculate.append((RuntimeVariable.FinalLineCoverage, line_cov_ff))
    elif config.CoverageMetric.LINE in cov_metrics:
        # If we optimised for lines, we still want to get the final line coverage.
        to_calculate.append((
            RuntimeVariable.FinalLineCoverage,
            _get_coverage_ff_from_algorithm(algorithm, ff.TestSuiteLineCoverageFunction),
        ))
    if (
        RuntimeVariable.FinalBranchCoverage in output_variables
        and config.CoverageMetric.BRANCH not in cov_metrics
    ):
        metrics_for_reinstrumentation.add(config.CoverageMetric.BRANCH)
        branch_cov_ff = ff.TestSuiteBranchCoverageFunction(executor)
        to_calculate.append((RuntimeVariable.FinalBranchCoverage, branch_cov_ff))
    elif config.CoverageMetric.BRANCH in cov_metrics:
        # If we optimised for branches, we still want to get the final branch coverage.
        to_calculate.append((
            RuntimeVariable.FinalBranchCoverage,
            _get_coverage_ff_from_algorithm(algorithm, ff.TestSuiteBranchCoverageFunction),
        ))


def _run() -> ReturnCode:  # noqa: C901
    _verify_config()
    if (setup_result := _setup_and_check()) is None:
        return ReturnCode.SETUP_FAILED
    executor, test_cluster, constant_provider = setup_result
    # traces slices for test cases after execution
    coverage_metrics = config.configuration.statistics_output.coverage_metrics
    if config.CoverageMetric.CHECKED in coverage_metrics:
        executor.add_remote_observer(RemoteStatementSlicingObserver())

    algorithm: GenerationAlgorithm = _instantiate_test_generation_strategy(
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
    executor.clear_remote_observers()

    _track_search_metrics(algorithm, generation_result, coverage_metrics)
    try:
        _LOGGER.info("Minimizing test cases")
        _minimize(generation_result, algorithm)
    except Exception as ex:
        _LOGGER.exception("Minimization failed: %s", ex)
    _generate_assertions(executor, generation_result, test_cluster)

    if (
        tracked_metrics := _track_final_metrics(
            algorithm,
            executor,
            generation_result,
            constant_provider,
        )
    ) is None:
        return ReturnCode.FINAL_METRICS_TRACKING_FAILED

    executor.subject_properties.instrumentation_tracer.disable()

    # Export the generated test suites
    if config.configuration.test_case_output.export_strategy == config.ExportStrategy.PY_TEST:
        try:
            _export_chromosome(generation_result)
        except Exception as ex:
            _LOGGER.exception("Export to PyTest failed: %s", ex)

    if config.configuration.statistics_output.create_coverage_report:
        try:
            coverage_report = get_coverage_report(
                generation_result,
                executor.subject_properties,
                tracked_metrics,
            )
            render_coverage_report(
                coverage_report,
                Path(config.configuration.statistics_output.report_dir) / "cov_report.html",
                datetime.datetime.now(),  # noqa: DTZ005
            )
            render_xml_coverage_report(
                coverage_report,
                Path(config.configuration.statistics_output.report_dir) / "cov_report.xml",
                datetime.datetime.now(),  # noqa: DTZ005
            )
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to create coverage report: %s. ",
                e,
            )
    _collect_miscellaneous_statistics(test_cluster)
    if not stat.write_statistics():
        _LOGGER.error("Failed to write statistics data")
    if generation_result.size() == 0:
        # not able to generate one test case
        return ReturnCode.NO_TESTS_GENERATED
    return ReturnCode.OK


def _run_llm() -> ReturnCode:
    def load_sut_code() -> str:
        project_path = Path(config.configuration.project_path)
        module_name = config.configuration.module_name.replace(".", "/") + ".py"
        sut_file = project_path / module_name
        return sut_file.read_text()

    model = LLM.create(LLMProvider.OPENAI)
    user_prompt = "Generate test cases for the following Python code:\n\n"
    user_prompt += "```\n"
    user_prompt += load_sut_code()
    user_prompt += "\n```\n"
    response = model.chat(user_prompt)
    if not response:
        return ReturnCode.NO_TESTS_GENERATED

    code = extract_code(response)
    module_name = config.configuration.module_name.replace(".", "_")
    target_file = (
        Path(config.configuration.test_case_output.output_path).resolve() / f"test_{module_name}.py"
    )
    target_file.write_text(code)
    return ReturnCode.OK


def _check_coverage(original_coverages: list[float], minimized_coverages: list[float]) -> bool:
    """Check if the coverage after minimization is the same as before.

    Args:
        original_coverages: The coverages before minimization
        minimized_coverages: The coverages after minimization

    Returns:
        If the coverage is still the same
    """
    is_same = all(map(math.isclose, original_coverages, minimized_coverages))
    if is_same:
        _LOGGER.info("Coverage after minimization is the same as before: %s", minimized_coverages)
    else:
        _LOGGER.warning(
            "Coverage after minimization changed from %s to %s",
            original_coverages,
            minimized_coverages,
        )
    return is_same


def _minimize(generation_result, algorithm=None):
    truncation = pp.ExceptionTruncation()
    generation_result.accept(truncation)
    if config.configuration.test_case_output.post_process:
        unused_vars_minimizer = pp.UnusedStatementsTestCaseVisitor()
        minimization_strategy = (
            config.configuration.test_case_output.minimization.test_case_minimization_strategy
        )

        if minimization_strategy != config.MinimizationStrategy.NONE and algorithm is not None:
            fitness_functions = algorithm.test_suite_coverage_functions
            assert len(fitness_functions) > 0, "No test suite coverage functions available"
            original_coverages = [
                generation_result.get_coverage_for(fitness_function)
                for fitness_function in fitness_functions
            ]

            # Save a copy of the original test suite before minimization
            original_test_suite = generation_result.clone()

            # Select the appropriate minimization visitor based on the strategy
            if (
                config.configuration.test_case_output.minimization.test_case_minimization_direction
                == config.MinimizationDirection.FORWARD
            ):
                iterative_minimizer: pp.IterativeMinimizationVisitor = (
                    pp.ForwardIterativeMinimizationVisitor(fitness_functions)
                )
            else:
                iterative_minimizer = pp.BackwardIterativeMinimizationVisitor(fitness_functions)

            # Check if we should use the combined minimization approach
            if (
                config.configuration.test_case_output.minimization.test_case_minimization_strategy
                == config.MinimizationStrategy.COMBINED
            ):
                combined_minimizer = pp.CombinedMinimizationVisitor(fitness_functions)
                generation_result.accept(combined_minimizer)

                _LOGGER.info(
                    "Combined minimization removed %d statement(s)",
                    combined_minimizer.removed_statements,
                )
            else:
                # Apply traditional test case minimization strategies
                test_case_minimizer = pp.TestCasePostProcessor([
                    unused_vars_minimizer,
                    iterative_minimizer,
                ])
                generation_result.accept(test_case_minimizer)

                _LOGGER.info(
                    "Removed %d statement(s) from test casesusing %s minimization",
                    iterative_minimizer.removed_statements,
                    minimization_strategy.value,
                )

                # Apply test suite minimization to remove redundant test cases
                if (
                    config.configuration.test_case_output.minimization.test_case_minimization_strategy
                    == config.MinimizationStrategy.SUITE
                ):
                    test_suite_minimizer = pp.TestSuiteMinimizationVisitor(fitness_functions)
                    generation_result.accept(test_suite_minimizer)

                    if test_suite_minimizer.removed_test_cases > 0:
                        _LOGGER.info(
                            "Removed %d test case(s) from test suite during minimization",
                            test_suite_minimizer.removed_test_cases,
                        )

            minimized_coverages = [
                generation_result.get_coverage_for(fitness_function)
                for fitness_function in fitness_functions
            ]
            is_same = _check_coverage(original_coverages, minimized_coverages)
            if not is_same:
                # Restore unminimized test suite
                _LOGGER.info("Restoring unminimized test suite due to coverage loss")
                # Replace the current test suite with the original one
                generation_result.test_case_chromosomes = [
                    test.clone() for test in original_test_suite.test_case_chromosomes
                ]
                # Mark the test suite as changed
                generation_result.changed = True
                # Verify that coverage is restored
                restored_coverage = generation_result.get_coverage_for(fitness_functions)
                _LOGGER.info("Coverage after restoration: %.4f", restored_coverage)

        else:
            unused_primitives_removal = pp.TestCasePostProcessor([unused_vars_minimizer])
            generation_result.accept(unused_primitives_removal)

    # Remove empty test cases after minimization
    empty_test_case_remover = pp.EmptyTestCaseRemover()
    generation_result.accept(empty_test_case_remover)


def _minimize_assertions(generation_result: tsc.TestSuiteChromosome):
    _LOGGER.info("Minimizing assertions based on checked coverage")
    assertion_minimizer = pp.AssertionMinimization()
    generation_result.accept(assertion_minimizer)
    stat.track_output_variable(
        RuntimeVariable.Assertions, len(assertion_minimizer.remaining_assertions)
    )
    stat.track_output_variable(
        RuntimeVariable.DeletedAssertions,
        len(assertion_minimizer.deleted_assertions),
    )


_strategies: dict[config.MutationStrategy, Callable[[int], ms.HOMStrategy]] = {
    config.MutationStrategy.FIRST_TO_LAST: ms.FirstToLastHOMStrategy,
    config.MutationStrategy.BETWEEN_OPERATORS: ms.BetweenOperatorsHOMStrategy,
    config.MutationStrategy.RANDOM: ms.RandomHOMStrategy,
    config.MutationStrategy.EACH_CHOICE: ms.EachChoiceHOMStrategy,
}


def _setup_mutant_generator() -> mu.Mutator:
    operators: list[type[MutationOperator]] = [
        *mo.standard_operators,
        *mo.experimental_operators,
    ]

    mutation_strategy = config.configuration.test_case_output.mutation_strategy

    if mutation_strategy == config.MutationStrategy.FIRST_ORDER_MUTANTS:
        return mu.FirstOrderMutator(operators)

    order = config.configuration.test_case_output.mutation_order

    if order <= 0:
        raise ConfigurationException("Mutation order should be > 0.")

    if mutation_strategy in _strategies:
        hom_strategy = _strategies[mutation_strategy](order)
        return mu.HighOrderMutator(operators, hom_strategy=hom_strategy)

    raise ConfigurationException("No suitable mutation strategy found.")


def _setup_mutation_analysis_assertion_generator(
    executor: TestCaseExecutor,
) -> ag.MutationAnalysisAssertionGenerator:
    _LOGGER.info("Setup mutation generator")
    mutant_generator = _setup_mutant_generator()

    _LOGGER.info("Import module %s", config.configuration.module_name)
    module = importlib.import_module(config.configuration.module_name)

    _LOGGER.info("Build AST for %s", module.__name__)
    module_source_code = inspect.getsource(module)
    module_ast = ParentNodeTransformer.create_ast(module_source_code)

    _LOGGER.info("Mutate module %s", module.__name__)
    mutation_controller = MutationController(mutant_generator, module_ast, module)
    assertion_generator: ag.MutationAnalysisAssertionGenerator
    if config.configuration.test_case_output.assertion_generation is config.AssertionGenerator.LLM:
        assertion_generator = lag.MutationAnalysisLLMAssertionGenerator(
            executor, mutation_controller
        )
    else:
        assertion_generator = ag.MutationAnalysisAssertionGenerator(executor, mutation_controller)

    _LOGGER.info("Generated %d mutants", mutation_controller.mutant_count())
    return assertion_generator


def _generate_assertions(executor, generation_result, test_cluster):
    ass_gen = config.configuration.test_case_output.assertion_generation
    if ass_gen != config.AssertionGenerator.NONE:
        _LOGGER.info("Start generating assertions")
        generator: cv.ChromosomeVisitor
        if ass_gen == config.AssertionGenerator.LLM:
            generation_result.accept(lag.LLMAssertionGenerator(test_cluster))
            generator = _setup_mutation_analysis_assertion_generator(executor)
        elif ass_gen == config.AssertionGenerator.MUTATION_ANALYSIS:
            generator = _setup_mutation_analysis_assertion_generator(executor)
        else:
            generator = ag.AssertionGenerator(executor)
        generation_result.accept(generator)


def _track_search_metrics(
    algorithm: GenerationAlgorithm,
    generation_result: tsc.TestSuiteChromosome,
    coverage_metrics: list[config.CoverageMetric],
) -> None:
    """Track multiple set coverage metrics of the generated test suites.

    This possibly re-executes the test suites.

    Args:
        algorithm: The test generation strategy
        generation_result:  The resulting chromosome of the generation strategy
        coverage_metrics: The selected coverage metrics to guide the search
    """
    for metric, runtime, fitness_type in [
        (
            config.CoverageMetric.LINE,
            RuntimeVariable.LineCoverage,
            ff.TestSuiteLineCoverageFunction,
        ),
        (
            config.CoverageMetric.BRANCH,
            RuntimeVariable.BranchCoverage,
            ff.TestSuiteBranchCoverageFunction,
        ),
        (
            config.CoverageMetric.CHECKED,
            RuntimeVariable.StatementCheckedCoverage,
            ff.TestSuiteStatementCheckedCoverageFunction,
        ),
    ]:
        if metric in coverage_metrics:
            coverage_function: ff.TestSuiteCoverageFunction = _get_coverage_ff_from_algorithm(
                algorithm, cast("type", fitness_type)
            )
            stat.track_output_variable(
                runtime, generation_result.get_coverage_for(coverage_function)
            )
    # Write overall coverage data of result
    stat.current_individual(generation_result)


def _instantiate_test_generation_strategy(
    executor: TestCaseExecutor,
    test_cluster: ModuleTestCluster,
    constant_provider: ConstantProvider,
) -> GenerationAlgorithm:
    factory = gaf.TestSuiteGenerationAlgorithmFactory(executor, test_cluster, constant_provider)
    return factory.get_search_algorithm()


def _collect_miscellaneous_statistics(test_cluster: ModuleTestCluster) -> None:
    test_cluster.log_cluster_statistics()
    stat.track_output_variable(RuntimeVariable.TargetModule, config.configuration.module_name)
    stat.track_output_variable(RuntimeVariable.RandomSeed, randomness.RNG.get_seed())
    stat.track_output_variable(
        RuntimeVariable.ConfigurationId,
        config.configuration.statistics_output.configuration_id,
    )
    stat.track_output_variable(RuntimeVariable.RunId, config.configuration.statistics_output.run_id)
    stat.track_output_variable(
        RuntimeVariable.ProjectName, config.configuration.statistics_output.project_name
    )
    for runtime_variable, value in stat.variables_generator:
        stat.set_output_variable_for_runtime_variable(runtime_variable, value)


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
    module_name = config.configuration.module_name.replace(".", "_")
    target_file = (
        Path(config.configuration.test_case_output.output_path).resolve()
        / f"test_{module_name}{file_name_suffix}.py"
    )
    store_call_return = (
        config.configuration.test_case_output.assertion_generation is config.AssertionGenerator.LLM
    )
    export_visitor = export.PyTestChromosomeToAstVisitor(store_call_return=store_call_return)

    chromosome.accept(export_visitor)
    export.save_module_to_file(
        export_visitor.to_module(),
        target_file,
        format_with_black=config.configuration.test_case_output.format_with_black,
    )
    _LOGGER.info("Written %i test cases to %s", chromosome.size(), target_file)
