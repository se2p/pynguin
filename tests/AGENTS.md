<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# tests/

<!-- Parent: ../AGENTS.md -->

## Purpose

This directory contains the comprehensive test suite for Pynguin, mirroring the source code structure in `src/`. The test suite uses pytest with extensive fixtures and utilities for testing automated test generation, including unit tests for all major components: genetic algorithms, instrumentation, assertion generation, type system analysis, and test execution.

## Key Files

| File | Purpose |
|------|---------|
| `conftest.py` | Pytest configuration with extensive shared fixtures (test cases, mocks, type system, control flow graphs, bytecode examples) |
| `testutils.py` | Testing utilities for type system feeding, mutation assertions, module imports, and test case extraction |
| `test_cli.py` | Tests for command-line interface parsing and execution |
| `test_generator.py` | Tests for the main test generation orchestration logic |
| `test___main__.py` | Tests for direct module execution |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `analyses/` | Tests for static analysis components (type inference, module analysis, seeding, constants, syntax trees) |
| `assertion/` | Tests for assertion generation and mutation analysis operators |
| `fixtures/` | Test fixtures including example Python modules for testing (cluster, examples, instrumentation, coverage scenarios) |
| `ga/` | Tests for genetic algorithm components (chromosomes, operators, fitness, coverage goals, stopping conditions) |
| `instrumentation/` | Tests for bytecode instrumentation and execution tracing |
| `large_language_model/` | Tests for LLM integration and test generation |
| `master_worker/` | Tests for distributed execution architecture |
| `resources/` | Test resources and configuration files |
| `slicer/` | Tests for dynamic program slicing |
| `testcase/` | Tests for test case representation, statements, execution, and visitors |
| `utils/` | Tests for utility modules (statistics, type utilities, atomic counters, namespaces) |

## For AI Agents

### Testing Patterns

**Fixture Usage:**
- `conftest.py` provides auto-used fixtures: `reset_configuration()` resets the Configuration singleton before each test
- Common fixtures: `default_test_case`, `type_system`, `constructor_mock`, `method_mock`, `function_mock`, `field_mock`
- CFG fixtures: `small_control_flow_graph`, `larger_control_flow_graph`, `yield_control_flow_graph`
- Bytecode fixtures: `conditional_jump_example_bytecode` (version-specific Python 3.10-3.14)
- Pre-built test fixtures: `plus_test_with_object_assertion`, `exception_test_with_except_assertion`, etc.

**Test Structure:**
- Tests mirror the `src/` directory structure exactly
- Each source module typically has a corresponding `test_*.py` file
- Complex components have subdirectories with multiple test files

**Common Patterns:**
- Mock-based testing for external dependencies (executors, tracers, test clusters)
- Property-based testing patterns for genetic algorithm components
- Bytecode manipulation testing with version-specific conditional fixtures
- Mutation testing verification using `assert_mutation` and `assert_mutator_mutation` helpers

**Helper Functions (testutils.py):**
- `feed_typesystem()`: Aligns TypeInfo objects with a TypeSystem instance
- `assert_mutation()`: Verifies mutation operators produce expected AST transformations
- `assert_mutator_mutation()`: Verifies first-order mutators produce expected mutant sets
- `module_to_path()`: Converts module names to file paths
- `import_module_safe()`: Safely imports test modules with fallback mechanisms
- `instrument_function()`: Applies instrumentation transformations to functions
- `extract_test_case_0()`: Extracts first test case from generated test code

### Pytest Conventions

- **Autouse fixtures**: Configuration and statistics reset automatically before each test
- **Scope management**: Session-scoped fixtures for expensive setups (imported modules, CFGs)
- **Parametrization**: Used extensively for testing across multiple configurations
- **Markers**: Tests may use custom markers for categorization (not shown in conftest)
- **Mocking**: Extensive use of `unittest.mock.MagicMock` for isolation

### Important Test Categories

**Instrumentation Tests:**
- Bytecode transformation correctness across Python versions
- Control flow graph construction and analysis
- Execution tracing and coverage collection

**GA Tests:**
- Chromosome operations (crossover, mutation, selection)
- Fitness computation and caching
- Coverage goal satisfaction
- Stopping condition evaluation

**Type System Tests:**
- Type inference accuracy
- Generic type handling
- Type compatibility checking

**Assertion Tests:**
- Assertion mining from execution traces
- Mutation operator correctness
- Assertion minimization

### Dependencies

- **pytest**: Test framework and fixture management
- **bytecode**: Bytecode manipulation for instrumentation tests
- **unittest.mock**: Mocking framework for isolation
- **importlib**: Dynamic module loading for test fixtures
- **ast**: AST manipulation for mutation testing verification
- **tempfile**: Temporary test execution environments

### Working with Tests

When modifying source code:
1. Find corresponding test file(s) in matching `tests/` subdirectory
2. Run tests with `pytest tests/path/to/test_module.py`
3. Use fixtures from `conftest.py` to avoid setup duplication
4. Leverage `testutils.py` helpers for common assertion patterns
5. Check version-specific bytecode fixtures when working with instrumentation

When debugging test failures:
1. Check if `reset_configuration()` is properly resetting state
2. Verify TypeSystem alignment using `feed_typesystem()` if type-related
3. Use `-vv` flag for detailed assertion output
4. Check fixture scopes if seeing unexpected state persistence

---

**Generated:** 2026-01-30
**Updated:** 2026-01-30
