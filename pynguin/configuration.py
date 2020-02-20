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
from typing import Optional


class ExportStrategy(enum.Enum):
    """Contains all available export strategies."""

    PY_TEST_EXPORTER = "PY_TEST_EXPORTER"
    UNIT_TEST_EXPORTER = "UNIT_TEST_EXPORTER"
    NONE = "NONE"


class Algorithm(enum.Enum):
    """Different algorithms."""

    RANDOOPY = False
    WSPY = True

    def __init__(self, use_instrumentation: bool):
        self._use_instrumentation = use_instrumentation

    @property
    def use_instrumentation(self) -> bool:
        """Does this algorithm use instrumentation."""
        return self._use_instrumentation


class StoppingCondition(enum.Enum):
    """The different stopping conditions for the algorithms."""

    MAX_TIME = "MAX_TIME"
    MAX_ITERATIONS = "MAX_ITERATIONS"
    MAX_TESTS = "MAX_TESTS"


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

    # Measure coverage
    measure_coverage: bool = True

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

    # Bias for better individuals in rank selection
    rank_bias = 1.7

    # What condition should be checked to end the search/test generation.
    stopping_condition: StoppingCondition = StoppingCondition.MAX_TIME


# Singleton instance of the configuration.
INSTANCE = Configuration(
    algorithm=Algorithm.RANDOOPY, project_path="", output_path="", module_name=""
)
