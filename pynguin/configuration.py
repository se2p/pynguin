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

import pynguin.utils.statistics.statistics as stat  # pylint:disable=cyclic-import


class ExportStrategy(enum.Enum):
    """Contains all available export strategies."""

    PY_TEST_EXPORTER = "PY_TEST_EXPORTER"
    UNIT_TEST_EXPORTER = "UNIT_TEST_EXPORTER"
    NONE = "NONE"


class Algorithm(enum.Enum):
    """Different algorithms."""

    RANDOOPY = "RANDOOPY"
    RANDOOPY_MONKEYTYPE = "RANDOOPY_MONKEYTYPE"
    WSPY = "WSPY"


class StoppingCondition(enum.Enum):
    """The different stopping conditions for the algorithms."""

    MAX_TIME = "MAX_TIME"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    MAX_TESTS = "MAX_TESTS"


class TypeInferenceStrategy(enum.Enum):
    """The different available type-inference strategies."""

    NONE = "NoTypeInferenceStrategy"
    STUB_FILES = "StubInferenceStrategy"
    TYPE_HINTS = "TypeHintsInferenceStrategy"


class StatisticsBackend(enum.Enum):
    """The different available statistics backends to write statistics"""

    NONE = enum.auto()
    CONSOLE = enum.auto()
    CSV = enum.auto()


# pylint: disable=too-many-instance-attributes
@dataclasses.dataclass(repr=True, eq=True)
class Configuration:
    """General configuration for the test generator."""

    # The algorithm that shall be used for generation
    algorithm: Algorithm

    # Path to the project the generator shall create tests for.
    project_path: str

    # Path to an output folder for the generated test cases.
    output_path: str

    # A list of module names for that the generator shall create tests for.
    module_name: str

    # A predefined seed value for the random number generator that is used.
    seed: Optional[int] = None

    # Path to store the log file.
    log_file: Optional[str] = None

    # Enables the debug mode.
    # Some features might behave different when it is active.
    debug_mode: bool = False

    # Directory in which to put HTML and CSV reports
    report_dir: str = "pynguin-report"

    # Which backend to use to collect data
    statistics_backend: StatisticsBackend = StatisticsBackend.CSV

    # Time interval in nano-seconds for timeline statistics, i.e., we select a data
    # point after each interval.  This can be interpolated, if there is no exact
    # value stored at the time-step of the interval, see `timeline_interpolation`.
    # The default value is every 1.00s.
    timeline_interval: int = 1 * 1_000_000_000

    # Interpolate timeline values
    timeline_interpolation: bool = True

    # List of variables to output to the statistics backend.
    output_variables: List[stat.RuntimeVariable] = dataclasses.field(
        default_factory=lambda: [
            stat.RuntimeVariable.TargetModule,
            stat.RuntimeVariable.Coverage,
        ]
    )

    # Label that identifies the used configuration of Pynguin.  This is only done
    # when running experiments.
    configuration_id: str = ""

    # Time budget (in seconds) that can be used for generating tests.
    budget: int = 600

    # Maximum search duration
    search_budget: int = 60

    # Maximum iterations
    algorithm_iterations: int = 60

    # Maximum seconds allowed for entire search when not using time as stopping
    # criterion.
    global_timeout: int = 120

    # The maximum length of sequences that are generated, 0 means infinite.
    max_sequence_length: int = 10

    # The maximum number of combined sequences, 0 means infinite.
    max_sequences_combined: int = 10

    # The counter threshold for purging sequences, 0 means infinite.
    counter_threshold: int = 10

    # The export strategy determines for which test-runner system the
    # generated tests should fit.
    export_strategy: ExportStrategy = ExportStrategy.PY_TEST_EXPORTER

    # Recursion depth when trying to create objects
    max_recursion: int = 10

    # The maximum level of recursion when calculating the dependencies in the test
    # cluster
    max_cluster_recursion: int = 10

    # Maximum size of delta for numbers during mutation
    max_delta: int = 20

    # Maximum size of randomly generated integers (minimum range = -1 * max)
    max_int: int = 2048

    # Maximum length of randomly generated strings
    string_length: int = 20

    # Probability to reuse an existing primitive, if available.  Expects values in [0,1]
    primitive_reuse_probability: float = 0.5

    # Probability to reuse an existing object, if available.  Expects values in [0,1]
    object_reuse_probability: float = 0.9

    # Probability to use None instead of constructing an object.  Expects values in
    # [0,1]
    none_probability: float = 0.1

    # Should we guess unknown types while constructing parameters?
    # This might happen in the following cases:
    # The parameter type is unknown, e.g. a parameter is missing a type hint.
    # The parameter is not primitive and cannot be created from the test cluster,
    # e.g. Callable[...]
    guess_unknown_types: bool = True

    # Probability of replacing parameters when mutating a method or constructor statement
    # in a test case.  Expects values in [0,1]
    change_parameter_probability: float = 0.1

    # Bias for better individuals in rank selection
    rank_bias: float = 1.7

    # Minimum number of tests in initial test suites
    min_initial_tests: int = 1

    # Maximum number of tests in initial test suites
    max_initial_tests: int = 10

    # Population size of genetic algorithm
    population: int = 50

    # Chop statements after exception if length has reached maximum
    chop_max_length: bool = True

    # Elite size for search algorithm
    elite: int = 1

    # Maximum length of chromosomes during search
    chromosome_length: int = 40

    # Number of attempts when generating an object before giving up
    max_attempts: int = 1000

    # Score for selection of insertion of UUT calls
    insertion_uut: float = 0.5

    # Probability of crossover
    crossover_rate: float = 0.75

    # Initial probability of inserting a new test in a test suite
    test_insertion_probability: float = 0.1

    # Probability of deleting statements during mutation
    test_delete_probability: float = 1.0 / 3.0

    # Probability of changing statements during mutation
    test_change_probability: float = 1.0 / 3.0

    # Probability of inserting new statements during mutation
    test_insert_probability: float = 1.0 / 3.0

    # Initial probability of inserting a new statement in a test case
    statement_insertion_probability: float = 0.5

    # Maximum number of test cases in a test suite
    max_size: int = 100

    # What condition should be checked to end the search/test generation.
    stopping_condition: StoppingCondition = StoppingCondition.MAX_TIME

    # Execute MonkeyType in each n-th iteration of the algorithm
    monkey_type_execution: int = 1

    # The strategy for type-inference that shall be used
    type_inference_strategy: TypeInferenceStrategy = TypeInferenceStrategy.TYPE_HINTS

    # Path to the pyi-stub files for the StubInferenceStrategy
    stub_dir: Optional[str] = None

    # Should the generator use a static constant seeding technique to improve constant
    # generation?
    constant_seeding: bool = False


# Singleton instance of the configuration.
INSTANCE = Configuration(
    algorithm=Algorithm.RANDOOPY, project_path="", output_path="", module_name=""
)
