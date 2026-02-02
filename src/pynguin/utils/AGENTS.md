<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Utilities Module - AGENTS.md

<!-- Parent: ../AGENTS.md -->

Utility modules providing generic helpers, ML-specific tools, and statistics collection infrastructure.

**Location:** `/src/pynguin/utils/`

## Module Structure

```
utils/
├── Core Utilities (random number generation, naming, collections)
├── generic/ (generic algorithms and data structures)
├── pynguinml/ (ML-specific parameters and testing resources)
└── statistics/ (statistics tracking and output)
```

## Core Utilities (Root Level)

### Randomness Module
**File:** `randomness.py`
**Purpose:** Singleton random number generator with seed tracking

**Key Components:**
- `Random` class: Extends `random.Random` to track seed values
- `RNG` singleton: Global seeded random instance
- **Functions:**
  - `next_char()` - Random printable ASCII character
  - `next_string(length)` - Random string of given length
  - `next_int(lower_bound, upper_bound)` - Random integer in range
  - `next_float(lower_bound, upper_bound)` - Random float in range [0,1] default
  - `next_gaussian()` - Random value from Gaussian distribution (μ=0, σ=1)
  - `next_bool()` - Random boolean value
  - `next_byte()` / `next_bytes(length)` - Random byte(s)
  - `choice(sequence)` - Select random element from sequence
  - `choices(population, weights, k)` - K-sample with replacement
  - `weighted_choice(options)` - Pick callable by weight probabilities
  - `shuffle(sequence)` - In-place shuffle
  - `sample(population, num_elements)` - Sample without replacement

**Usage:** Central RNG for all test generation and search operations

---

### Naming Scope Module
**File:** `namingscope.py`
**Purpose:** Maps objects to unique human-friendly variable names

**Key Classes:**
- `AbstractNamingScope` - Interface for naming strategies
- `NamingScope` - Maps objects to numbered names (e.g., `var_0`, `var_1`)
  - Constructor: `prefix="var"`, optional `new_name_callback`
  - Methods: `get_name()`, `is_known_name()`, `__len__()`, `__iter__()`
- `VariableTypeNamingScope` - Names variables by their type
  - Uses static type annotations + optional runtime type trace
  - Generates names like `string_0`, `integer_1`
  - Supports return type traces for improved naming

**Helper Functions:**
- `snake_case(name)` - Convert CamelCase to snake_case

**Usage:** Test code generation, generating readable variable names in test cases

---

### Collection Utilities
**File:** `collection_utils.py`
**Purpose:** Generic dictionary and collection helpers

**Functions:**
- `dict_without_keys(dict, keys)` - Returns dict with specified keys removed

---

### AST Utilities
**File:** `ast_util.py`
**Purpose:** Abstract Syntax Tree manipulation

**Functions:**
- AST node creation and inspection utilities
- Node type checking and transformation

---

### Atomic Integer
**File:** `atomicinteger.py`
**Purpose:** Thread-safe integer counter for concurrent access

---

### Mutation Utilities
**File:** `mutation_utils.py`
**Purpose:** Helper functions for genetic algorithm mutations

---

### Configuration Writer
**File:** `configuration_writer.py`
**Purpose:** Serializes configuration objects to file formats

---

### Control Flow Distance
**File:** `controlflowdistance.py`
**Purpose:** Calculates control flow distances for test guidance

---

### Exceptions
**File:** `exceptions.py`
**Purpose:** Custom exception types

**Key Exceptions:**
- `ConstraintValidationError` - Parameter constraint violations

---

### Execution Recorder
**File:** `execution_recorder.py`
**Purpose:** Records execution traces during test runs

---

### File System Isolation
**File:** `fs_isolation.py`
**Purpose:** Safe sandbox for file system operations during test execution

---

### LLM Utilities
**File:** `llm.py`
**Purpose:** Large Language Model integration helpers

---

### Logging Utilities
**File:** `logging_utils.py`
**Purpose:** Centralized logging configuration

---

### Mirror
**File:** `mirror.py`
**Purpose:** Runtime reflection utilities

---

## Generic Module
**Location:** `/src/pynguin/utils/generic/`

Generic algorithms and data structures supporting test generation.

**Modules:**
- Generic algorithmic utilities
- Data structure helpers
- Common algorithmic patterns

---

## ML Module
**Location:** `/src/pynguin/utils/pynguinml/`

Machine Learning-specific testing infrastructure.

### ML Parameter Module
**File:** `mlparameter.py`
**Purpose:** Representation of ML-specific parameters

**Key Classes:**
- `MLParameter` - Stores ML parameter information
  - Parses parameter constraints (shape, dtype, value ranges)
  - Validates constraints during initialization
  - Supports NumPy dtype mapping for framework-specific dtypes
  - Common NumPy dtypes: int32, int64, float32, float64, complex64, complex128, bool, str

**Features:**
- Constraint validation for ML parameters
- Support for dtype conversion and mapping
- Parameter name and constraint tracking

---

### ML Parsing Utilities
**File:** `ml_parsing_utils.py`
**Purpose:** Parse ML framework specifications and parameter definitions

---

### ML Test Factory Utilities
**File:** `ml_testfactory_utils.py`
**Purpose:** Factory methods for ML test generation

---

### ML Testing Resources
**File:** `ml_testing_resources.py`
**Purpose:** Resources and fixtures for ML test cases

---

### NumPy RNG
**File:** `np_rng.py`
**Purpose:** NumPy random number generator integration

---

## Statistics Module
**Location:** `/src/pynguin/utils/statistics/`

Statistics tracking and reporting infrastructure.

### Statistics Backend
**File:** `statisticsbackend.py`
**Purpose:** Abstract interface for statistics output

**Key Classes:**
- `OutputVariable[T]` - Dataclass wrapping statistic value and name
  - Fields: `name: str`, `value: T`
- `AbstractStatisticsBackend` - Interface for statistics writers
  - Method: `write_data(data: dict[str, OutputVariable])`
- `CSVStatisticsBackend` - Writes statistics to CSV file
  - Appends to `statistics.csv` in report directory
  - Writes header on first write (empty file detection)
  - Handles quoting and large field sizes
- `ConsoleStatisticsBackend` - Debug output to console

**Usage:** Pluggable statistics export mechanism

---

### Statistics Tracker
**File:** `stats.py`
**Purpose:** Central singleton for runtime variable tracking

**Key Classes:**
- `_StatisticsTracker` - Singleton tracking runtime variables
  - Uses thread-safe `queue.Queue` for variable buffering
  - Tracks `RuntimeVariable` + value pairs
  - Properties: `variables`, `variables_generator`
  - Methods: `reset()`, `track_output_variable()`

**Features:**
- Queue-based async variable tracking
- Generator interface for consuming tracked variables
- Search statistics aggregation
- Thread-safe operation

---

### Runtime Variable
**File:** `runtimevariable.py`
**Purpose:** Definition of runtime variables for tracking

**Key Classes:**
- `RuntimeVariable` - Descriptor for trackable statistics
  - Defines variable metadata (name, type, initial value)
  - Used in statistics collection pipeline

---

### Statistics Observer
**File:** `statisticsobserver.py`
**Purpose:** Observer pattern for statistics events

**Key Classes:**
- `StatisticsObserver` - Listens to statistics changes
- Integrates with tracker and backends

---

### Output Variable Factory
**File:** `outputvariablefactory.py`
**Purpose:** Factory for creating output variable definitions

**Functions:**
- Creates `OutputVariable` instances
- Maps internal tracking variables to output format
- Handles type conversion and formatting

---

## Integration Points

### With Test Generation
- `randomness.RNG` - All test case mutations and random choices
- `namingscope` - Variable naming in generated test code
- `statistics` - Fitness and coverage tracking during search

### With ML Testing
- `pynguinml.MLParameter` - Parameter constraints for ML models
- `pynguinml.ml_testing_resources` - ML test fixtures
- `pynguinml.np_rng` - NumPy array generation

### With Reporting
- `statistics.statisticsbackend` - Pluggable output formats
- `statistics.stats` - Aggregated metrics collection
- `configuration_writer` - Config serialization

---

## Key Design Patterns

1. **Singleton Pattern:** `randomness.RNG` - Single seeded RNG instance
2. **Strategy Pattern:** Naming scopes (`NamingScope`, `VariableTypeNamingScope`)
3. **Observer Pattern:** Statistics tracking with pluggable backends
4. **Factory Pattern:** Output variable creation
5. **Queue Pattern:** Thread-safe variable tracking

---

## Common Usage Examples

```python
# Random value generation
from pynguin.utils.randomness import RNG, next_int, next_bool

seed = RNG.get_seed()
random_int = next_int(0, 100)
random_bool = next_bool()

# Variable naming
from pynguin.utils.namingscope import NamingScope

scope = NamingScope(prefix="arg")
var_name = scope.get_name(some_object)  # "arg_0", "arg_1", ...

# Statistics tracking
from pynguin.utils.statistics.stats import STATISTICS_TRACKER
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

STATISTICS_TRACKER.track_output_variable(SOME_VARIABLE, 42)
```

---

## Testing Considerations

- Randomness module provides deterministic seeding for reproducible tests
- Statistics tracker can be reset between test runs
- File system isolation prevents test pollution
- ML parameter validation catches invalid configurations early

---

*Documentation timestamp: 2026-01-30*

*Parent directory: `/src/pynguin/`*
