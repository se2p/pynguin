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
from typing import List


class ExportStrategy(enum.Enum):
    """Contains all available export strategies."""

    PY_TEST_EXPORTER = "PY_TEST_EXPORTER"
    UNIT_TEST_EXPORTER = "UNIT_TEST_EXPORTER"
    NONE = "NONE"


class Verbosity(enum.Enum):
    """Different verbosity levels."""

    QUIET = "QUIET"
    NORMAL = "NORMAL"
    VERBOSE = "VERBOSE"


class Algorithm(enum.Enum):
    """Different algorithms."""

    RANDOOPY = "RANDOOPY"
    WSPY = "WSPY"


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
    module_names: List[str]

    # A predefined seed value for the random number generator that is used.
    seed: int = 42

    # Time budget (in seconds) that can be used for generating tests.
    budget: int = 600

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

    # Probability to reuse an existing primitive, if available.  Expects values in [0,1]
    primitive_reuse_probability: float = 0.5

    # Probability to reuse an existing object, if available.  Expects values in [0,1]
    object_reuse_probability: float = 0.9

    # Probability to use None instead of constructing an object.  Expects values in
    # [0,1]
    none_probability: float = 0.1


# Singleton instance of the configuration.
INSTANCE = Configuration(
    algorithm=Algorithm.RANDOOPY, project_path="", output_path="", module_names=[]
)
