<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Assertion Tests

**Parent:** `../AGENTS.md`

Test suite for pynguin's assertion generation, insertion, and validation system.

## Directory Structure

### Core Assertion Components

- **`test_assertion.py`** - Assertion statement representation
  - Assertion creation and initialization
  - Expected value representation
  - Assertion validation logic
  - Assertion comparison semantics

- **`test_assertioninsertionstategy.py`** - Assertion insertion strategies
  - Selecting where to insert assertions
  - Assertion placement heuristics
  - Statement coverage analysis
  - Assertion prioritization

- **`test_primitiveassertiongen.py`** - Primitive value assertions
  - Asserting on primitive types
  - Value comparison assertions
  - Type-specific assertion generation
  - Literal value assertions

### Advanced Assertion Generation

- **`test_asyncassertions.py`** - Async code assertions
  - Assertions in async test cases
  - Awaitable result assertions
  - Async context handling
  - Coroutine assertions

- **`test_contractassertions.py`** - Contract-based assertions
  - Pre-condition assertions
  - Post-condition assertions
  - Invariant assertions
  - Contract violation detection

- **`test_deltadebugging.py`** - Assertion minimization
  - Removing redundant assertions
  - Assertion simplification
  - False positive elimination
  - Minimal assertion sets

- **`test_typeguardassertions.py`** - Type guard assertions
  - Type checking assertions
  - Instance checking
  - Protocol assertions
  - Type constraint assertions

### Assertion Analysis

- **`test_assertiontraceexecution.py`** - Execution trace analysis
  - Capturing execution traces
  - Trace-based assertion generation
  - Variable value tracking
  - State change detection

- **`test_assertionobjectproperties.py`** - Object property assertions
  - Asserting object attributes
  - Property value checking
  - Method return value assertions
  - Object state assertions

- **`test_comparisionassertions.py`** - Comparison-based assertions
  - Equality assertions
  - Ordering assertions (< > <= >=)
  - Container membership assertions
  - Pattern-based assertions

## Test Organization

### By Feature

| Feature | Test Module | Purpose |
|---------|-------------|---------|
| Basics | `test_assertion.py` | Core assertion representation |
| Insertion | `test_assertioninsertionstategy.py` | Assertion placement |
| Primitives | `test_primitiveassertiongen.py` | Primitive type assertions |
| Async | `test_asyncassertions.py` | Async code handling |
| Contracts | `test_contractassertions.py` | Contract-based testing |
| Minimization | `test_deltadebugging.py` | Assertion cleanup |
| Type Guards | `test_typeguardassertions.py` | Type assertions |
| Traces | `test_assertiontraceexecution.py` | Trace-based generation |
| Properties | `test_assertionobjectproperties.py` | Object assertions |
| Comparison | `test_comparisionassertiongen.py` | Comparison assertions |

### Statistics

- **Total Test Files:** 20 Python files
- **Total Size:** Comprehensive assertion subsystem coverage
- **Test Methods:** 50+ individual test functions

## Key Testing Areas

1. **Assertion Representation**
   - Assertion statement structure
   - Expected value encoding
   - Assertion types (equality, comparison, etc.)
   - Assertion semantics

2. **Assertion Generation**
   - Inferring assertions from execution
   - Type-based assertion generation
   - State change detection
   - Value comparison discovery

3. **Assertion Insertion**
   - Placing assertions in test cases
   - Avoiding redundant assertions
   - Maximizing coverage utility
   - Maintaining readability

4. **Type-Specific Assertions**
   - Primitive type assertions
   - Container assertions
   - Object attribute assertions
   - Type guard assertions

5. **Advanced Strategies**
   - Contract-based assertions
   - Async code assertions
   - Property-based assertions
   - Trace-driven assertions

6. **Assertion Minimization**
   - Removing redundant assertions
   - Simplifying assertion conditions
   - Eliminating false positives
   - Reducing test noise

7. **Validation and Checking**
   - Assertion correctness
   - Expected value accuracy
   - Type consistency
   - False positive detection

## Assertion Generation Pipeline

Tests verify assertion generation workflow:

1. **Test Execution** (`test_assertiontraceexecution.py`)
   - Run test case
   - Capture execution trace
   - Record variable values
   - Track state changes

2. **Analysis** (multiple modules)
   - Analyze trace for patterns
   - Identify interesting values
   - Detect invariants
   - Find comparisons

3. **Generation** (type-specific modules)
   - Create assertion statements
   - Encode expected values
   - Set assertion types
   - Format output

4. **Insertion** (`test_assertioninsertionstategy.py`)
   - Choose insertion points
   - Evaluate statement coverage
   - Optimize assertion placement
   - Ensure validity

5. **Minimization** (`test_deltadebugging.py`)
   - Remove redundant assertions
   - Simplify conditions
   - Detect false positives
   - Finalize assertion set

## Assertion Types

Tests cover assertion categories:

- **Equality Assertions** - `==`, `!=`
- **Ordering Assertions** - `<`, `>`, `<=`, `>=`
- **Membership Assertions** - `in`, `not in`
- **Type Assertions** - `isinstance()`, `issubclass()`
- **Containment Assertions** - Container member checks
- **Exception Assertions** - Expected exceptions
- **Property Assertions** - Object attribute values
- **Method Assertions** - Return value assertions

## Integration Points

Assertion tests verify integration with:
- **Test Case System** - Adding assertions to test cases
- **Type System** - Type-aware assertion generation
- **Execution Engine** - Running tests with assertions
- **GA System** - Using assertions as fitness feedback
- **Instrumentation** - Type information for assertions

## Assertion Quality Metrics

Tests verify assertion quality:

- **Correctness** - Assertions are valid Python
- **Relevance** - Assertions check meaningful properties
- **Minimality** - No redundant assertions
- **Readability** - Clear and understandable
- **Coverage Utility** - Assertions improve test quality
- **Type Safety** - Assertions respect types
- **Performance** - Assertions are efficient

## Delta Debugging

Tests verify delta debugging algorithm:
- Systematic assertion removal
- Minimal failing assertion sets
- Redundancy identification
- False positive detection
- Iterative simplification

See individual test files for specific assertion generation strategies.
