#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a configuration interface for the test generator."""

import dataclasses
import enum
import time

from pynguin.utils.statistics.runtimevariable import RuntimeVariable


class ExportStrategy(str, enum.Enum):
    """Contains all available export strategies.

    These strategies allow to export the generated test cases in different styles,
    such as the style of the `PyTest` framework.  Setting the value to `NONE` will
    prevent exporting of the generated test cases (only reasonable for
    benchmarking, though).
    """

    PY_TEST = "PY_TEST"
    """Export tests in the style of the PyTest framework."""

    NONE = "NONE"
    """Do not export test cases at all."""


class Algorithm(str, enum.Enum):
    """Different algorithms supported by Pynguin."""

    DYNAMOSA = "DYNAMOSA"
    """The dynamic many-objective sorting algorithm (cf. Panichella et al. Automated
    test case generation as a many-objective optimisation problem with dynamic selection
    of the targets.  TSE vol. 44 issue 2)."""

    LLM = "LLM"
    """Query a large language model for tests.  NOTE: This does not execute the usual test and
    assertion generation stages of Pynguin but queries an LLM and writes the resulting test cases to
    the output file."""

    MIO = "MIO"
    """The MIO test suite generation algorithm (cf. Andrea Arcuri. Many Independent
    Objective (MIO) Algorithm for Test Suite Generation.  Proc. SBSE 2017)."""

    MOSA = "MOSA"
    """The many-objective sorting algorithm (cf. Panichella et al. Reformulating Branch
    Coverage as a Many-Objective Optimization Problem.  Proc. ICST 2015)."""

    LLMOSA = "LLMOSA"
    """The many-objective sorting algorithm with LLM."""

    RANDOM = "RANDOM"
    """A feedback-direct random test generation approach similar to the algorithm
    proposed by Randoop (cf. Pacheco et al. Feedback-directed random test generation.
    Proc. ICSE 2007)."""

    RANDOM_TEST_SUITE_SEARCH = "RANDOM_TEST_SUITE_SEARCH"
    """Performs random search on test suites."""

    RANDOM_TEST_CASE_SEARCH = "RANDOM_TEST_CASE_SEARCH"
    """Performs random search on test cases."""

    WHOLE_SUITE = "WHOLE_SUITE"
    """A whole-suite test generation approach similar to the one proposed by EvoSuite
    (cf. Fraser and Arcuri. EvoSuite: Automatic Test Suite Generation for
    Object-Oriented Software. Proc. ESEC/FSE 2011).

    This algorithm can be modified to use an archive (cf. Rojas, José Miguel, et al.
    "A detailed investigation of the effectiveness of whole test suite generation."
    Empirical Software Engineering 22.2 (2017): 852-893.), by using the
    following options: --use-archive True, --seed-from-archive True and
    --filter-covered-targets-from-test-cluster True.
    """


class AssertionGenerator(str, enum.Enum):
    """Different approaches for assertion generation supported by Pynguin."""

    LLM = "LLM"
    """Use Large Language Model(LLM) for assertion generation."""

    MUTATION_ANALYSIS = "MUTATION_ANALYSIS"
    """Use the mutation analysis approach for assertion generation."""

    CHECKED_MINIMIZING = "CHECKED_MINIMIZING"
    """All assertions that do not increase the checked coverage are removed."""

    SIMPLE = "SIMPLE"
    """Use the simple approach for primitive and none assertion generation."""

    NONE = "NONE"
    """Do not create any assertions."""


class MutationStrategy(str, enum.Enum):
    """Different strategies for creating mutants.

    Only respected when using the MUTATION_ANALYSIS approach for assertion generation.
    """

    FIRST_ORDER_MUTANTS = "FIRST_ORDER_MUTANTS"
    """Generate first order mutants."""

    FIRST_TO_LAST = "FIRST_TO_LAST"
    """Higher order mutation strategy FirstToLast.
    (cf. Mateo et al. Validating Second-Order Mutation at System Level. Article.
    IEEE Transactions on SE 39.4 2013)"""

    BETWEEN_OPERATORS = "BETWEEN_OPERATORS"
    """Higher order mutation strategy BetweenOperators.
    (cf. Mateo et al. Validating Second-Order Mutation at System Level. Article.
    IEEE Transactions on SE 39.4 2013)"""

    RANDOM = "RANDOM"
    """Higher order mutation strategy Random.
    (cf. Mateo et al. Validating Second-Order Mutation at System Level. Article.
    IEEE Transactions on SE 39.4 2013)"""

    EACH_CHOICE = "EACH_CHOICE"
    """Higher order mutation strategy EachChoice.
    (cf. Mateo et al. Validating Second-Order Mutation at System Level. Article.
    IEEE Transactions on SE 39.4 2013)"""


class MinimizationDirection(str, enum.Enum):
    """Directions for test case minimization.

    Either start with the first statement and try removing it and all forward dependent
    statements, or start with the last statement and try removing it and all backward
    dependent statements.
    """

    FORWARD = "FORWARD"
    """Apply forward minimization, which removes statements from the beginning to the end."""

    BACKWARD = "BACKWARD"
    """Apply backward minimization, which removes statements from the end to the beginning."""


class MinimizationStrategy(str, enum.Enum):
    """Different strategies for minimizing test cases."""

    NONE = "NONE"
    """Do not apply any minimization."""

    CASE = "CASE"
    """Apply minimization at the test case level."""

    SUITE = "SUITE"
    """Apply minimization at the test suite level, i.e., remove entire test cases that
    do not contribute to the coverage of the module under test."""

    COMBINED = "COMBINED"
    """Apply minimization at the test case level but check against all test cases in the suite."""


class TypeInferenceStrategy(str, enum.Enum):
    """The different available type-inference strategies."""

    NONE = "NONE"
    """Ignore any type information given in the module under test."""

    TYPE_HINTS = "TYPE_HINTS"
    """Use type information from type hints in the module under test."""


class StatisticsBackend(str, enum.Enum):
    """The different available statistics backends to write statistics."""

    NONE = "NONE"
    """Do not write any statistics."""

    CONSOLE = "CONSOLE"
    """Write statistics to the standard out."""

    CSV = "CSV"
    """Write statistics to a CSV file."""


class CoverageMetric(str, enum.Enum):
    """The different available coverage metrics available for optimisation."""

    BRANCH = "BRANCH"
    """Calculate how many of the possible branches in the code were executed"""

    LINE = "LINE"
    """Calculate how many of the possible lines in the code were executed"""

    CHECKED = "CHECKED"
    """Calculate how many of the possible lines in the
    code are checked by an assertion."""


class Selection(str, enum.Enum):
    """Different selection algorithms to select from."""

    RANK_SELECTION = "RANK_SELECTION"
    """Rank selection."""

    TOURNAMENT_SELECTION = "TOURNAMENT_SELECTION"
    """Tournament selection.  Use `tournament_size` to set size."""


@dataclasses.dataclass
class StatisticsOutputConfiguration:
    """Configuration related to output."""

    report_dir: str = "pynguin-report"
    """Directory in which to put HTML and CSV reports"""

    statistics_backend: StatisticsBackend = StatisticsBackend.CSV
    """Which backend to use to collect data"""

    timeline_interval: int = 1 * 1_000_000_000
    """Time interval in nano-seconds for timeline statistics, i.e., we select a data
    point after each interval.  This can be interpolated, if there is no exact
    value stored at the time-step of the interval, see `timeline_interpolation`.
    The default value is every 1.00s."""

    timeline_interpolation: bool = True
    """Interpolate timeline values"""

    coverage_metrics: list[CoverageMetric] = dataclasses.field(
        default_factory=lambda: [CoverageMetric.BRANCH]
    )
    """List of coverage metrics that are optimised during the search"""

    output_variables: list[RuntimeVariable] = dataclasses.field(
        default_factory=lambda: [
            RuntimeVariable.TargetModule,
            RuntimeVariable.Coverage,
        ]
    )
    """List of variables to output to the statistics backend."""

    configuration_id: str = ""
    """Label that identifies the used configuration of Pynguin.  This is only done
    when running experiments."""

    run_id: str = ""
    """Id of the cluster run. Useful for finding the log entries that belong to a
    certain result."""

    project_name: str = ""
    """Label that identifies the project name of Pynguin.  This is useful when
    running experiments."""

    create_coverage_report: bool = False
    """Create a coverage report for the tested module.
    This can be helpful to find hard to cover parts because Pynguin measures coverage
    on bytecode level which might yield different results when compared with other
    tools, e.g., Coverage.py."""

    type_guess_top_n: int = 10
    """When exporting type guesses for parameters, how many guesses per parameter
    should be exported? Expects positive integers."""


@dataclasses.dataclass
class Minimization:
    """Configuration for test case minimization."""

    test_case_minimization_strategy: MinimizationStrategy = MinimizationStrategy.CASE
    """Strategy to apply for minimizing test cases to remove redundant statements
    while preserving fitness."""

    test_case_minimization_direction: MinimizationDirection = MinimizationDirection.BACKWARD
    """Direction to apply for minimizing test cases."""


@dataclasses.dataclass
class TestCaseOutputConfiguration:
    """Configuration related to test case output."""

    output_path: str
    """Path to an output folder for the generated test cases."""

    crash_path: str = ""
    """Path to an output folder for the generated test cases that caused a crash.
    Only works when running in a subprocess. If set to "", the are stored in the
    output_path."""

    export_strategy: ExportStrategy = ExportStrategy.PY_TEST
    """The export strategy determines for which test-runner system the
    generated tests should fit."""

    max_length_test_case: int = 2500
    """The maximum number of statement in as test case (normal + assertion
    statements)"""

    assertion_generation: AssertionGenerator = AssertionGenerator.MUTATION_ANALYSIS
    """The generator that shall be used for assertion generation."""

    allow_stale_assertions: bool = False
    """Allow assertion on things that did not change between statement executions."""

    mutation_strategy: MutationStrategy = MutationStrategy.FIRST_ORDER_MUTANTS
    """The strategy that shall be used for creating mutants in the mutation analysis
    assertion generation method."""

    mutation_order: int = 1
    """The order of the generated higher order mutants in the mutation analysis
    assertion generation method."""

    post_process: bool = True
    """Should the results be post processed? For example, truncate test cases after
    statements that raise an exception."""

    minimization: Minimization = Minimization(
        test_case_minimization_strategy=MinimizationStrategy.CASE,
        test_case_minimization_direction=MinimizationDirection.BACKWARD,
    )
    """Strategy to apply for minimizing test cases."""

    float_precision: float = 0.01
    """Precision to use in float comparisons and assertions"""

    format_with_black: bool = True
    """Format the generated test cases using black."""


@dataclasses.dataclass
class SeedingConfiguration:
    """Configuration related to seeding."""

    seed: int = time.time_ns()
    """A predefined seed value for the random number generator that is used."""

    constant_seeding: bool = True
    """Should the generator use a static constant seeding technique to improve constant
    generation?"""

    initial_population_seeding: bool = False
    """Should the generator use previously existing testcases to seed the initial
    population?"""

    initial_population_data: str = ""
    """The path to the file with the pre-existing tests. The path has to include the
    file itself."""

    seeded_testcases_reuse_probability: float = 0.9
    """Probability of using seeded testcases when initial population seeding is
    enabled."""

    initial_population_mutations: int = 0
    """Number of how often the testcases collected by initial population seeding should
    be mutated to promote diversity"""

    dynamic_constant_seeding: bool = True
    """Enables seeding of constants at runtime."""

    seeded_primitives_reuse_probability: float = 0.2
    """Probability for using seeded primitive values instead of randomly
    generated ones."""

    seeded_dynamic_values_reuse_probability: float = 0.6
    """Probability of using dynamically seeded values when a primitive seeded
     value will be used."""

    seed_from_archive: bool = False
    """When sampling new test cases reuse some from the archive, if one is used."""

    seed_from_archive_probability: float = 0.2
    """Instead of creating a new test case, reuse a covering solution from the archive,
    iff an archive is used."""

    seed_from_archive_mutations: int = 3
    """Number of mutations applied when sampling from the archive."""

    max_dynamic_length: int = 1000
    """Maximum length of strings/bytes that should be stored in the dynamic constant
    pool."""

    max_dynamic_pool_size: int = 50
    """Maximum number of constants of the same type that should be stored in the
    dynamic constant pool."""


@dataclasses.dataclass
class MIOPhaseConfiguration:
    """Configuration for a phase of MIO."""

    number_of_tests_per_target: int
    """Number of test cases for each target goal to keep in an archive."""

    random_test_or_from_archive_probability: float
    """Probability [0,1] of sampling a new test at random or choose an existing one in
    an archive."""

    number_of_mutations: int
    """Number of mutations allowed to be done on the same individual before
    sampling a new one."""


@dataclasses.dataclass
class MIOConfiguration:
    """Configuration that is specific to the MIO approach."""

    initial_config: MIOPhaseConfiguration = dataclasses.field(
        default_factory=lambda: MIOPhaseConfiguration(
            number_of_tests_per_target=10,
            random_test_or_from_archive_probability=0.5,
            number_of_mutations=1,
        )
    )
    """Configuration to use before focused phase."""

    focused_config: MIOPhaseConfiguration = dataclasses.field(
        default_factory=lambda: MIOPhaseConfiguration(
            number_of_tests_per_target=1,
            random_test_or_from_archive_probability=0.0,
            number_of_mutations=10,
        )
    )
    """Configuration to use in focused phase"""

    exploitation_starts_at_percent: float = 0.5
    """Percentage ]0,1] of search budget after which exploitation is activated, i.e.,
    switching to focused phase."""


@dataclasses.dataclass
class RandomConfiguration:
    """Configuration that is specific to the RANDOM approach."""

    max_sequence_length: int = 10
    """The maximum length of sequences that are generated, 0 means infinite."""

    max_sequences_combined: int = 10
    """The maximum number of combined sequences, 0 means infinite."""


@dataclasses.dataclass
class TypeInferenceConfiguration:
    """Configuration related to type inference."""

    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS
    """The strategy for type-inference that shall be used"""

    type_tracing: bool | float = 0.0
    """Probability to trace usage of parameters with unknown types to improve type
    guesses during test execution. Type tracing requires a separate second.
    The value should be a float in [0,1]. Boolean is kept for backwards compatibility
    as Python internally converts True to 1.0 and False to 0.0 anyways."""


@dataclasses.dataclass
class PynguinMLConfiguration:
    """Configurations for PynguinML, specifically for machine learning API testing."""

    ml_testing_enabled: bool = False
    """
    Enables ML-based test generation using API constraints. When set to True, PynguinML
    will use constraints and other ML-specific behaviours during input generation.

    Note: 'constraints_path' must also be set to locate the constraints files.
    """

    constraints_path: str = ""
    """
    Directory path to YAML/JSON constraints files.
    """

    dtype_mapping_path: str = ""
    """
    Path to a YAML/JSON file that maps library-specific datatypes to NumPy datatypes.
    Used by PynguinML for input generation. Specify only valid NumPy dtypes without
    the "np." prefix. Example: "torch.int32" -> "int32".
    """

    constructor_function: str = ""
    """
    Optional constructor function to build tensors (e.g., torch.tensor or
    tensorflow.convert_to_tensor). Must accept a np.ndarray as input.
    Note: Also set 'constructor_function_parameter' to specify which parameter
    receives the np.ndarray.
    """

    constructor_function_parameter: str = ""
    """
    Name of the parameter in the constructor function that receives the np.ndarray.
    Must be set when 'constructor_function' is specified.
    """

    max_ndim: int = 4
    """
    Maximum number of dimensions of the tensors.
    If set too big, it can cause memory errors due to large tensor sizes.
    """

    max_shape_dim: int = 4
    """
    Maximum size of a dimension of a shape.
    If set too big, it can cause memory errors due to large tensor sizes.
    """

    ignore_constraints_probability: float = 0.25
    """
    Probability of ignoring constraints and falling back to Pynguin's default
    behavior when constructing statements.
    """


@dataclasses.dataclass
class TestCreationConfiguration:
    """Configuration related to test creation."""

    max_recursion: int = 10
    """Recursion depth when trying to create objects in a test case."""

    max_delta: int = 20
    """Maximum size of delta for numbers during mutation"""

    max_int: int = 2048
    """Maximum size of randomly generated integers (minimum range = -1 * max)"""

    string_length: int = 20
    """Maximum length of randomly generated strings"""

    bytes_length: int = 20
    """Maximum length of randomly generated bytes"""

    collection_size: int = 5
    """Maximum length of randomly generated collections"""

    primitive_reuse_probability: float = 0.5
    """Probability to reuse an existing primitive in a test case, if available.
    Expects values in [0,1]"""

    object_reuse_probability: float = 0.9
    """Probability to reuse an existing object in a test case, if available.
    Expects values in [0,1]"""

    none_weight: float = 1
    """Weight to use None as parameter type during test generation.
    Expects values > 0."""

    any_weight: float = 5
    """Weight to use Any as parameter type during test generation.
    Expects values > 0."""

    original_type_weight: float = 5
    """Weight to use the originally annotated type as parameter type during test
    generation. Expects values > 0."""

    type_tracing_weight: float = 10
    """Weight to use the type guessed from type tracing as parameter type during
    test generation. Expects values > 0."""

    type4py_weight: float = 10
    """Weight to use types inferred from type4py as parameter type during
    test generation. Expects values > 0."""

    type_tracing_kept_guesses: int = 2
    """Amount of kept recently guessed types per parameter, when type tracing
    is used."""

    wrap_var_param_type_probability: float = 0.7
    """Probability to wrap the type required for a ``*arg`` or ``**kwargs`` parameter
    in a list or dict, respectively. Expects values in [0,1]"""

    negate_type: float = 0.1
    """When inferring a type from proxies, it may also be desirable to negate the chosen
    type, e.g., such that an instance check or a getattr() evaluate to False.
    Expects values in [0,1]"""

    skip_optional_parameter_probability: float = 0.7
    """Probability to skip an optional parameter, i.e., do not fill such a parameter."""

    max_attempts: int = 1000
    """Number of attempts when generating an object before giving up"""

    insertion_uut: float = 0.5
    """Score for selection of insertion of UUT calls"""

    max_size: int = 100
    """Maximum number of test cases in a test suite"""

    use_random_object_for_call: float = 0.1
    """When adding or modifying a call on an object, use a random modifier instead
    of only modifiers for that type. Expects values in [0, 1]."""


@dataclasses.dataclass
class SearchAlgorithmConfiguration:
    """General configuration for search algorithms."""

    min_initial_tests: int = 1
    """Minimum number of tests in initial test suites"""

    max_initial_tests: int = 10
    """Maximum number of tests in initial test suites"""

    population: int = 50
    """Population size of genetic algorithm"""

    chromosome_length: int = 40
    """Maximum length of chromosomes during search"""

    chop_max_length: bool = True
    """Chop statements after exception if length has reached maximum"""

    elite: int = 1
    """Elite size for search algorithm"""

    crossover_rate: float = 0.75
    """Probability of crossover"""

    test_insertion_probability: float = 0.1
    """Initial probability of inserting a new test in a test suite"""

    test_delete_probability: float = 1.0 / 3.0
    """Probability of deleting statements during mutation"""

    test_change_probability: float = 1.0 / 3.0
    """Probability of changing statements during mutation"""

    test_insert_probability: float = 1.0 / 3.0
    """Probability of inserting new statements during mutation"""

    statement_insertion_probability: float = 0.5
    """Initial probability of inserting a new statement in a test case"""

    random_perturbation: float = 0.2
    """Probability to replace a primitive with a random new value rather than adding
    a delta."""

    change_parameter_probability: float = 0.1
    """Probability of replacing parameters when mutating a method or constructor
    statement in a test case.  Expects values in [0,1]"""

    tournament_size: int = 5
    """Number of individuals for tournament selection."""

    rank_bias: float = 1.7
    """Bias for better individuals in rank selection"""

    selection: Selection = Selection.TOURNAMENT_SELECTION
    """The selection operator for genetic algorithms."""

    use_archive: bool = False
    """Some algorithms can be enhanced with an optional archive, e.g. Whole Suite ->
    Whole Suite + Archive. Use this option to enable the usage of an archive.
    Algorithms that always use an archive are not affected by this option."""

    filter_covered_targets_from_test_cluster: bool = False
    """Focus search by filtering out elements from the test cluster when
     they are fully covered."""

    number_of_mutations: int = 1
    """Number of mutations that should be applied in one breeding step."""


@dataclasses.dataclass
class StoppingConfiguration:
    """Configuration related to when Pynguin should stop.

    Note that these are mostly soft-limits rather than hard limits, because
    the search algorithms only check the condition at the start of each algorithm
    iteration.
    """

    maximum_search_time: int = -1
    """Time (in seconds) that can be used for generating tests."""

    maximum_test_executions: int = -1
    """Maximum number of test cases to be executed."""

    maximum_statement_executions: int = -1
    """Maximum number of test cases to be executed."""

    maximum_slicing_time: int = 600
    """Time budget (in seconds) that can be used for slicing."""

    maximum_iterations: int = -1
    """Maximum iterations"""

    maximum_test_execution_timeout: int = 5
    """The maximum time (in seconds) after which a test case times out."""

    maximum_coverage: int = 100
    """The maximum percentage of coverage after which the generation shall stop."""

    maximum_coverage_plateau: int = -1
    """Maximum number of algorithm iterations without coverage change before the
    algorithms stops."""

    minimum_coverage: int = 100
    """Minimum coverage for the plateau-based stopping condition.  Expects values larger
    than 0 but less than 100 to activate the stopping condition; also requires the
    setting of minimum_plateau_iterations."""

    minimum_plateau_iterations: int = -1
    """Minimum iterations without a coverage change to stop early.  Expects values
    larger than 0; also requires the setting of minimum_coverage."""

    maximum_memory: int = 3000
    """Maximum memory usage in MB after which the generation shall stop.
    Expects values in MB greater than 0 of -1 to disable the check."""

    test_execution_time_per_statement: int = 1
    """The time (in seconds) per statement that a test is allowed to run
    (up to maximum_test_execution_timeout)."""


@dataclasses.dataclass
class LLMConfiguration:
    """Configuration for the LLM."""

    api_key: str = ""
    """The api key to call OpenAI LLM with."""

    model_name: str = "gpt-4o-mini"
    """The OpenAI Model to use for completions."""

    temperature: float = 0.8
    """The temperature to use when querying the model.
    The value must be from [0.0, 1.0]."""

    hybrid_initial_population: bool = False
    """Whether to include the LLM test cases in the initial population."""

    llm_test_case_percentage: float = 0.5
    """The percentage of LLM test cases in on the initial population. The value must
     be from [0.0, 1.0]."""

    enable_response_caching: bool = False
    """Whether to enable caching for responses of the model."""

    call_llm_for_uncovered_targets: bool = False
    """Whether to call the LLM for the uncovered targets initially."""

    coverage_threshold: float = 1
    """The coverage threshold when to call the LLM for low-coverage targets.
    The value must be from [0.0, 1.0]."""

    call_llm_on_stall_detection: bool = False
    """Whether to call the LLM for the uncovered targets in coverage stalls."""

    max_plateau_len: int = 25
    """The number of iterations to allow before soliciting the LLM."""

    max_llm_interventions: int = 1
    """The maximum number of allowed LLM interventions."""


@dataclasses.dataclass
class Configuration:
    """General configuration for the test generator."""

    project_path: str
    """Path to the project the generator shall create tests for."""

    module_name: str
    """Name of the module for which the generator shall create tests."""

    test_case_output: TestCaseOutputConfiguration
    """Configuration for how test cases should be output."""

    algorithm: Algorithm = Algorithm.DYNAMOSA
    """The algorithm that shall be used for generation."""

    statistics_output: StatisticsOutputConfiguration = dataclasses.field(
        default_factory=StatisticsOutputConfiguration
    )
    """Statistic Output configuration."""

    stopping: StoppingConfiguration = dataclasses.field(default_factory=StoppingConfiguration)
    """Stopping configuration."""

    large_language_model: LLMConfiguration = dataclasses.field(default_factory=LLMConfiguration)
    """Large Language Model(LLM) configuration."""

    seeding: SeedingConfiguration = dataclasses.field(default_factory=SeedingConfiguration)
    """Seeding configuration."""

    type_inference: TypeInferenceConfiguration = dataclasses.field(
        default_factory=TypeInferenceConfiguration
    )
    """Type inference configuration."""

    pynguinml: PynguinMLConfiguration = dataclasses.field(default_factory=PynguinMLConfiguration)
    """PynguinML configuration."""

    test_creation: TestCreationConfiguration = dataclasses.field(
        default_factory=TestCreationConfiguration
    )
    """Test creation configuration."""

    search_algorithm: SearchAlgorithmConfiguration = dataclasses.field(
        default_factory=SearchAlgorithmConfiguration
    )
    """Search algorithm configuration."""

    mio: MIOConfiguration = dataclasses.field(default_factory=MIOConfiguration)
    """Configuration used for the MIO algorithm."""

    random: RandomConfiguration = dataclasses.field(default_factory=RandomConfiguration)
    """Configuration used for the RANDOM algorithm."""

    ignore_modules: list[str] = dataclasses.field(default_factory=list)
    """Ignore the modules specified here from the module analysis."""

    ignore_methods: list[str] = dataclasses.field(default_factory=list)
    """Ignore the methods specified here from the module analysis."""

    subprocess: bool = False
    """Run the test generation in a subprocess."""

    subprocess_if_recommended: bool = True
    """Use the subprocess mode if the SUT analysis recommends it based on used
    C extension modules."""


# Singleton instance of the configuration.
configuration = Configuration(
    project_path="",
    module_name="",
    test_case_output=TestCaseOutputConfiguration(output_path=""),
)
