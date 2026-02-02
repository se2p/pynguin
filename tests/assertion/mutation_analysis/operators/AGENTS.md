<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Mutation Operators Test Suite

<!-- Parent: ../../AGENTS.md -->

**Purpose**: Tests for mutation operators to ensure they correctly generate mutants and maintain AST integrity.

## Overview

This test suite validates the mutation operators' ability to:
- Correctly identify and generate mutations
- Preserve AST structure and line numbers
- Handle edge cases (empty collections, None values, etc.)
- Generate valid Python AST that can be compiled

## Test Organization

Tests are organized by operator type, mirroring the source structure:

- `test_arithmetic.py` - Tests for ArithmeticOperatorDeletion and ArithmeticOperatorReplacement
- `test_logical.py` - Tests for BooleanReplacement and ComparisonOperatorReplacement
- `test_loop.py` - Tests for BreakContinueReplacement
- `test_exception.py` - Tests for exception handling operators
- `test_inheritance.py` - Tests for OO mutation operators
- `test_decorator.py` - Tests for decorator mutations
- `test_misc.py` - Tests for miscellaneous operators
- `test_base.py` - Tests for base mutation infrastructure

## Key Testing Patterns

### Mutation Generation Validation

Each test typically:
1. Creates test AST code snippet
2. Instantiates mutation operator
3. Collects all mutations by visiting AST
4. Validates count and correctness of generated mutations
5. Verifies each mutation compiles to valid Python

### Edge Case Coverage

- Empty/None values
- Nested structures (nested loops, nested exceptions)
- Mixed operators (arithmetic in comparisons)
- Real-world code patterns from Pynguin codebase

### Compilation Checks

Generated mutants are compiled to verify:
- AST structure is valid
- Line numbers are correct
- No syntax errors introduced

## Integration Points

### Input Dependencies

- **AST Module**: Uses ast.parse() to create test code
- **Source Operators**: Tests import and instantiate operators from parent module
- **Python Compiler**: Compiles generated mutants to verify validity

### Output Dependencies

- **CI/CD**: Test results feed into continuous integration
- **Coverage**: Mutation operator coverage tracked by test suite
- **Regression Detection**: Tests catch operator regressions

## Related Documentation

- Parent: [../../AGENTS.md](../../AGENTS.md) - Mutation analysis test subsystem
- [../../mutation_analysis/operators/AGENTS.md](../../mutation_analysis/operators/AGENTS.md) - Source operators

---

*Generated: 2026-01-30*
*Module: tests.assertion.mutation_analysis.operators*
