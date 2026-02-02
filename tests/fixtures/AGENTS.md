<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Pynguin Test Fixtures

**Parent:** `../AGENTS.md`

Test fixtures organized by feature category. These provide concrete example code for testing various pynguin subsystems.

## Directory Structure

### Core Coverage Categories

- **`cluster/`** - Type clustering and module analysis fixtures
  - Class definitions with various dependency patterns
  - Inheritance hierarchies (diamond patterns, etc.)
  - Lambda functions, nested functions, async code
  - File: `33 modules` testing class analysis and clustering

- **`instrumentation/`** - Code instrumentation and transformation fixtures
  - Modules for testing bytecode instrumentation
  - Coverage tracking target code
  - File: `13 modules` for instrumentation transformations

- **`examples/`** - General example modules
  - Sample code for GA testing
  - Type inference examples
  - File: `30 modules` covering various scenarios

### Coverage & Analysis

- **`linecoverage/`** - Line coverage measurement
  - Code with branching for line coverage tracking
  - File: `10 modules`

- **`branchcoverage/`** - Branch coverage measurement
  - Conditional code for branch coverage analysis
  - File: `9 modules`

- **`mutation/`** - Mutation testing fixtures
  - Mutatable code patterns
  - File: `8 modules`

- **`programgraph/`** - Program graph analysis
  - Code for CFG (control flow graph) building
  - File: `7 modules`

### Specialized Testing

- **`slicer/`** - Program slicing
  - Code for slicing analysis
  - File: `13 modules`

- **`seeding/`** - Test seeding strategies
  - `dynamicseeding/` - Dynamic seed collection
  - `initialpopulationseeding/` - Initial population seeding
  - `staticconstantseeding/` - Static constant discovery
  - File: `7 modules`

- **`regression/`** - Regression testing
  - Historical test cases and patterns
  - File: `7 modules`

- **`type_tracing/`** - Type inference by tracing
  - Runtime type information collection
  - File: `8 modules`

- **`types/`** - Type annotation handling
  - Generic types, type hints, annotations
  - File: `7 modules`

### Specialized Categories

- **`accessibles/`** - Accessibility patterns
  - Public/protected/private member testing
  - File: `5 modules`

- **`grammar/`** - Grammar-based testing
  - Grammar patterns and rules
  - File: `5 modules`

- **`errors/`** - Error handling
  - Exception raising and catching
  - File: `5 modules`

- **`crash/`** - Crash scenarios
  - Code that may crash or fail
  - File: `6 modules`

- **`duckmock/`** - Duck typing and mocking
  - Mock objects for testing
  - File: `4 modules`

- **`c/`** - C interop (if applicable)
  - File: `5 modules`

## Statistics

- **Total Fixtures:** ~151 Python modules
- **Total Subdirectories:** 25 feature-based categories
- **Coverage:** Unit test fixtures for all major pynguin subsystems

## Key Test Targets

These fixtures are used by tests in:
- `tests/ga/` - Genetic algorithm tests
- `tests/instrumentation/` - Instrumentation tests
- `tests/assertion/` - Assertion tests
- `tests/testcase/` - Test case representation tests

## Usage Pattern

Each fixture module contains concrete code examples used to verify pynguin's ability to:
1. Analyze and understand code structure
2. Instrument code for coverage tracking
3. Generate test cases
4. Assess mutation score
5. Trace runtime types

See individual subdirectory documentation for specific fixture purposes.
