#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
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

    MIO = "MIO"
    """The MIO test suite generation algorithm (cf. Andrea Arcuri. Many Independent
    Objective (MIO) Algorithm for Test Suite Generation.  Proc. SBSE 2017)."""

    MOSA = "MOSA"
    """The many-objective sorting algorithm (cf. Panichella et al. Reformulating Branch
    Coverage as a Many-Objective Optimization Problem.  Proc. ICST 2015)."""

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

    MUTATION_ANALYSIS = "MUTATION_ANALYSIS"
    """Use the mutation analysis approach for assertion generation."""

    SIMPLE = "SIMPLE"
    """Use the simple approach for primitive and none assertion generation."""

    NONE = "NONE"
    """Do not create any assertions."""


class MutationStrategy(str, enum.Enum):
    """Different strategies for creating mutants when using the MUTATION_ANALYSIS
    approach for assertion generation."""

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


class TypeInferenceStrategy(str, enum.Enum):
    """The different available type-inference strategies."""

    NONE = "NONE"
    """Ignore any type information given in the module under test."""

    STUB_FILES = "STUB_FILES"
    """Use type information from stub files."""

    TYPE_HINTS = "TYPE_HINTS"
    """Use type information from type hints in the module under test."""


class StatisticsBackend(str, enum.Enum):
    """The different available statistics backends to write statistics"""

    NONE = "NONE"
    """Do not write any statistics."""

    CONSOLE = "CONSOLE"
    """Write statistics to the standard out."""

    CSV = "CSV"
    """Write statistics to a CSV file."""


class CoverageMetric(str, enum.Enum):
    """The different available coverage metrics available for optimisation"""

    BRANCH = "BRANCH"
    """Calculate how many of the possible branches in the code were executed"""

    LINE = "LINE"
    """Calculate how many of the possible lines in the code were executed"""


class Selection(str, enum.Enum):
    """Different selection algorithms to select from."""

    RANK_SELECTION = "RANK_SELECTION"
    """Rank selection."""

    TOURNAMENT_SELECTION = "TOURNAMENT_SELECTION"
    """Tournament selection.  Use `tournament_size` to set size."""


# pylint:disable=too-many-instance-attributes
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
        default_factory=lambda: [
            CoverageMetric.BRANCH,
        ]
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

    project_name: str = ""
    """Label that identifies the project name of Pynguin.  This is useful when
    running experiments."""

    create_coverage_report: bool = False
    """Create a coverage report for the tested module.
    This can be helpful to find hard to cover parts because Pynguin measures coverage
    on bytecode level which might yield different results when compared with other
    tools, e.g., Coverage.py."""


@dataclasses.dataclass
class TestCaseOutputConfiguration:
    """Configuration related to test case output."""

    output_path: str
    """Path to an output folder for the generated test cases."""

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

    float_precision: float = 0.01
    """Precision to use in float comparisons and assertions"""


# pylint:disable=too-many-instance-attributes
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

    guess_unknown_types: bool = True
    """Should we guess unknown types while constructing parameters?
    This might happen in the following cases:
    The parameter type is unknown, e.g. a parameter is missing a type hint.
    The parameter is not primitive and cannot be created from the test cluster,
    e.g. Callable[...]"""

    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS
    """The strategy for type-inference that shall be used"""

    max_cluster_recursion: int = 10
    """The maximum level of recursion when calculating the dependencies in the test
    cluster."""

    stub_dir: str = ""
    """Path to the pyi-stub files for the StubInferenceStrategy"""


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

    none_probability: float = 0.1
    """Probability to use None in a test case instead of constructing an object.
    Expects values in [0,1]"""

    skip_optional_parameter_probability: float = 0.7
    """Probability to skip an optional parameter, i.e., do not fill this parameter."""

    max_attempts: int = 1000
    """Number of attempts when generating an object before giving up"""

    insertion_uut: float = 0.5
    """Score for selection of insertion of UUT calls"""

    max_size: int = 100
    """Maximum number of test cases in a test suite"""


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


@dataclasses.dataclass
class StoppingConfiguration:
    """Configuration related to when Pynguin should stop.
    Note that these are mostly soft-limits rather than hard limits, because
    the search algorithms only check the condition at the start of each algorithm
    iteration."""

    maximum_search_time: int = -1
    """Time (in seconds) that can be used for generating tests."""

    maximum_test_executions: int = -1
    """Maximum number of test cases to be executed."""

    maximum_statement_executions: int = -1
    """Maximum number of test cases to be executed."""

    maximum_iterations: int = -1
    """Maximum iterations"""


# pylint: disable=too-many-instance-attributes, pointless-string-statement
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

    stopping: StoppingConfiguration = dataclasses.field(
        default_factory=StoppingConfiguration
    )
    """Stopping configuration."""

    seeding: SeedingConfiguration = dataclasses.field(
        default_factory=SeedingConfiguration
    )
    """Seeding configuration."""

    type_inference: TypeInferenceConfiguration = dataclasses.field(
        default_factory=TypeInferenceConfiguration
    )
    """Type inference configuration."""

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


# Singleton instance of the configuration.
configuration = Configuration(
    project_path="",
    module_name="",
    test_case_output=TestCaseOutputConfiguration(output_path=""),
)
