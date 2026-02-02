<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Statistics Module - AGENTS.md

<!-- Parent: ../AGENTS.md -->

Statistics tracking and reporting infrastructure for test generation metrics and search performance analysis.

**Location:** `/src/pynguin/utils/statistics/`

## Module Overview

Centralized statistics collection and reporting system that tracks runtime metrics during test generation and search operations.

## Key Components

### Statistics Backend
**File:** `statisticsbackend.py`
**Purpose:** Abstract interface for statistics output

**Key Classes:**
- `OutputVariable[T]` - Dataclass wrapping statistic value and name
- `AbstractStatisticsBackend` - Interface for statistics writers
- `CSVStatisticsBackend` - Writes statistics to CSV file
- `ConsoleStatisticsBackend` - Debug output to console

### Statistics Tracker
**File:** `stats.py`
**Purpose:** Central singleton for runtime variable tracking

**Key Features:**
- Thread-safe queue-based variable buffering
- Tracks RuntimeVariable + value pairs
- Generator interface for consuming tracked variables
- Search statistics aggregation

### Runtime Variable
**File:** `runtimevariable.py`
**Purpose:** Definition of runtime variables for tracking

**Key Features:**
- Metadata for trackable statistics
- Variable type and initial value definition
- Used in statistics collection pipeline

### Statistics Observer
**File:** `statisticsobserver.py`
**Purpose:** Observer pattern for statistics events

### Output Variable Factory
**File:** `outputvariablefactory.py`
**Purpose:** Factory for creating output variable definitions

**Features:**
- Creates `OutputVariable` instances
- Maps internal tracking variables to output format
- Handles type conversion and formatting

## Architecture

```
Application Code
     ↓
STATISTICS_TRACKER (singleton)
     ↓
Statistics Backend Interface
     ├── CSV Backend (file output)
     ├── Console Backend (debug)
     └── Custom Backends (pluggable)
```

## Integration Points

### With Test Generation
- `statistics.stats` - Fitness and coverage tracking during search
- `runtime_variable` - Metric definitions
- `statisticsobserver` - Event listening

### With Reporting
- `statisticsbackend` - Pluggable output formats
- `outputvariablefactory` - Output formatting
- `configuration_writer` - Config serialization

## Common Usage Patterns

```python
# Statistics tracking
from pynguin.utils.statistics.stats import STATISTICS_TRACKER
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

STATISTICS_TRACKER.track_output_variable(SOME_VARIABLE, 42)

# Statistics output
from pynguin.utils.statistics.statisticsbackend import CSVStatisticsBackend

backend = CSVStatisticsBackend("report_dir")
backend.write_data({"metric": OutputVariable("metric", value)})
```

## Key Design Patterns

1. **Singleton Pattern** - Central STATISTICS_TRACKER instance
2. **Observer Pattern** - Statistics change notifications
3. **Strategy Pattern** - Pluggable backends for different output formats
4. **Factory Pattern** - Output variable creation
5. **Queue Pattern** - Thread-safe variable buffering

## Thread Safety

- Queue-based async variable tracking
- Thread-safe backend writes
- Atomic metric updates

## Testing Considerations

- Statistics tracker can be reset between test runs
- Multiple backends can be active simultaneously
- Variable tracking is non-blocking
- Format validation in output factories

---

*Documentation timestamp: 2026-01-30*

*Parent directory: `/src/pynguin/utils/`*
