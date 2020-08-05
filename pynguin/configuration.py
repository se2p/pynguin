# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides a configuration interface for the test generator."""
import dataclasses
import enum
from typing import List, Optional

from simple_parsing import Serializable

import pynguin.utils.statistics.statistics as stat  # pylint:disable=cyclic-import


class ExportStrategy(str, enum.Enum):
    """Contains all available export strategies.

    These strategies allow to export the generated test cases in different styles,
    such as in the style using the `unittest` library from the standard API or in the
    style of the `PyTest` framework.  Setting the value to `NONE` will prevent exporting
    of the generated test cases (only reasonable for benchmarking, though).
    """

    PY_TEST = "PY_TEST"
    """Export tests in the style of the PyTest framework."""

    UNIT_TEST = "UNIT_TEST"
    """Export tests in the style of the unittest library from standard API."""

    NONE = "NONE"
    """Do not export test cases at all."""


class Algorithm(str, enum.Enum):
    """Different algorithms supported by Pynguin."""

    RANDOOPY = "RANDOOPY"
    """A feedback-direct random test generation approach similar to the algorithm
    proposed by Randoop (cf. Pacheco et al. Feedback-directed random test generation.
    Proc. ICSE 2007)."""

    RANDOOPY_MONKEYTYPE = "RANDOOPY_MONKEYTYPE"

    WSPY = "WSPY"
    """A whole-suite test generation approach similar to the one proposed by EvoSuite
    (cf. Fraser and Arcuri. EvoSuite: Automatic Test Suite Generation for
    Object-Oriented Software. Proc. ESEC/FSE 2011)."""


class StoppingCondition(str, enum.Enum):
    """The different stopping conditions for the algorithms."""

    MAX_TIME = "MAX_TIME"
    """Stop after a maximum time limit has been reached."""

    MAX_ITERATIONS = "MAX_ITERATIONS"
    """Stop after a maximum number of algorithm iterations."""

    MAX_TESTS = "MAX_TESTS"
    """Stop as soon as a maximum number of tests was generated."""


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


# pylint: disable=too-many-instance-attributes, pointless-string-statement
@dataclasses.dataclass(repr=True, eq=True)
class Configuration(Serializable):
    """General configuration for the test generator."""

    algorithm: Algorithm
    """The algorithm that shall be used for generation"""

    project_path: str
    """Path to the project the generator shall create tests for."""

    output_path: str
    """Path to an output folder for the generated test cases."""

    module_name: str
    """A list of module names for that the generator shall create tests for."""

    seed: Optional[int] = None
    """A predefined seed value for the random number generator that is used."""

    debug_mode: bool = False
    """Enables the debug mode.
    Some features might behave different when it is active."""

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

    output_variables: List[stat.RuntimeVariable] = dataclasses.field(
        default_factory=lambda: [
            stat.RuntimeVariable.TargetModule,
            stat.RuntimeVariable.Coverage,
        ]
    )
    """List of variables to output to the statistics backend."""

    configuration_id: str = ""
    """Label that identifies the used configuration of Pynguin.  This is only done
    when running experiments."""

    budget: int = 600
    """Time budget (in seconds) that can be used for generating tests."""

    search_budget: int = 60
    """Maximum search duration"""

    algorithm_iterations: int = 60
    """Maximum iterations"""

    global_timeout: int = 120
    """Maximum seconds allowed for entire search when not using time as stopping
    criterion."""

    max_sequence_length: int = 10
    """The maximum length of sequences that are generated, 0 means infinite."""

    max_sequences_combined: int = 10
    """The maximum number of combined sequences, 0 means infinite."""

    counter_threshold: int = 10
    """The counter threshold for purging sequences, 0 means infinite."""

    export_strategy: ExportStrategy = ExportStrategy.PY_TEST
    """The export strategy determines for which test-runner system the
    generated tests should fit."""

    max_recursion: int = 10
    """Recursion depth when trying to create objects"""

    max_cluster_recursion: int = 10
    """The maximum level of recursion when calculating the dependencies in the test
    cluster"""

    max_delta: int = 20
    """Maximum size of delta for numbers during mutation"""

    max_int: int = 2048
    """Maximum size of randomly generated integers (minimum range = -1 * max)"""

    string_length: int = 20
    """Maximum length of randomly generated strings"""

    primitive_reuse_probability: float = 0.5
    """Probability to reuse an existing primitive, if available.  Expects values in
    [0,1]"""

    object_reuse_probability: float = 0.9
    """Probability to reuse an existing object, if available.  Expects values in
    [0,1]"""

    none_probability: float = 0.1
    """Probability to use None instead of constructing an object.  Expects values in
    [0,1]"""

    guess_unknown_types: bool = True
    """Should we guess unknown types while constructing parameters?
    This might happen in the following cases:
    The parameter type is unknown, e.g. a parameter is missing a type hint.
    The parameter is not primitive and cannot be created from the test cluster,
    e.g. Callable[...]"""

    change_parameter_probability: float = 0.1
    """Probability of replacing parameters when mutating a method or constructor statement
    in a test case.  Expects values in [0,1]"""

    rank_bias: float = 1.7
    """Bias for better individuals in rank selection"""

    min_initial_tests: int = 1
    """Minimum number of tests in initial test suites"""

    max_initial_tests: int = 10
    """Maximum number of tests in initial test suites"""

    population: int = 50
    """Population size of genetic algorithm"""

    chop_max_length: bool = True
    """Chop statements after exception if length has reached maximum"""

    elite: int = 1
    """Elite size for search algorithm"""

    chromosome_length: int = 40
    """Maximum length of chromosomes during search"""

    max_attempts: int = 1000
    """Number of attempts when generating an object before giving up"""

    insertion_uut: float = 0.5
    """Score for selection of insertion of UUT calls"""

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

    max_size: int = 100
    """Maximum number of test cases in a test suite"""

    stopping_condition: StoppingCondition = StoppingCondition.MAX_TIME
    """What condition should be checked to end the search/test generation."""

    monkey_type_execution: int = 1
    """Execute MonkeyType in each n-th iteration of the algorithm"""

    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS
    """The strategy for type-inference that shall be used"""

    stub_dir: Optional[str] = None
    """Path to the pyi-stub files for the StubInferenceStrategy"""

    constant_seeding: bool = False
    """Should the generator use a static constant seeding technique to improve constant
    generation?"""


# Singleton instance of the configuration.
INSTANCE = Configuration(
    algorithm=Algorithm.RANDOOPY, project_path="", output_path="", module_name=""
)
