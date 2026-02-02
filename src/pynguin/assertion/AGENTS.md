<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Assertion Generation Module

<!-- Parent: ../AGENTS.md -->

**Purpose**: Generates test assertions (oracles) to validate expected behavior of generated test cases.

## Overview

This module is responsible for creating assertions that make test cases meaningful. Without assertions, tests would only check if code runs without crashing. This module provides multiple strategies for assertion generation, including mutation analysis to ensure assertion quality.

## Key Components

### Core Assertion Types

**File**: `assertion.py`

Defines the assertion type hierarchy:

- **Assertion** (base class): Abstract base with visitor pattern support
- **ReferenceAssertion**: Assertions on a single variable reference
  - **TypeNameAssertion**: Checks type by module.qualname string comparison
  - **FloatAssertion**: Float equality with pytest.approx tolerance
  - **ObjectAssertion**: Direct equality checks for hashable/copyable objects
  - **IsInstanceAssertion**: isinstance() checks using AST representation
  - **CollectionLengthAssertion**: len() checks for collections with non-assertable elements
- **ExceptionAssertion**: Validates that an exception was raised

Uses visitor pattern (`AssertionVisitor`) for extensible processing.

### Assertion Generation Strategies

**File**: `assertiongenerator.py`

Three assertion generator implementations:

1. **AssertionGenerator** (base):
   - Executes tests and captures assertion traces
   - Filters flaky assertions through multiple executions
   - Removes stale assertions (values that haven't changed)
   - Respects max test case length configuration

2. **MutationAnalysisAssertionGenerator**:
   - Extends base generator with mutation testing
   - Creates mutants of the SUT using mutation operators
   - Runs tests against each mutant
   - Keeps only assertions that detect at least one mutant (mutation score filtering)
   - Provides mutation metrics: created/killed/timeout mutants, mutation score

3. **LLMAssertionGenerator** (`llmassertiongenerator.py`):
   - Uses Large Language Model to generate assertions
   - Unparsed test cases sent to LLM for assertion suggestions
   - Extracts `assert` statements from LLM response
   - Deserializes and integrates LLM assertions into test cases
   - **MutationAnalysisLLMAssertionGenerator**: Combines LLM + mutation filtering

### Assertion Trace System

**Files**: `assertion_trace.py`, `assertiontraceobserver.py`

Runtime assertion collection infrastructure:

- **AssertionTrace**: Maps statements to their generated assertions
- **AssertionVerificationTrace**: Tracks failed/error assertions during verification
- **RemoteAssertionTraceObserver**: Collects assertion data during test execution
- **RemoteAssertionVerificationObserver**: Validates assertions hold across executions

### AST Conversion

**File**: `assertion_to_ast.py`

Converts internal assertion objects to Python AST nodes for code generation:

- Implements `AssertionVisitor` to traverse assertion objects
- Generates appropriate AST for each assertion type
- Handles pytest.approx for floats
- Creates type name comparison strings
- Produces pytest.raises context managers for exceptions

## Mutation Analysis Subsystem

**Directory**: `mutation_analysis/`

Implements mutation testing to measure assertion quality.

### Architecture

**File**: `controller.py` - **MutationController**
- Orchestrates mutant creation and execution
- Yields (mutated_module, mutations) pairs
- Handles invalid mutants gracefully

**File**: `strategies.py` - Higher-Order Mutation (HOM) strategies:
- **FirstToLastHOMStrategy**: Combines first and last mutations
- **EachChoiceHOMStrategy**: Sequential mutation application
- **BetweenOperatorsHOMStrategy**: Ensures diverse operator coverage
- **RandomHOMStrategy**: Random mutation combinations

### Mutation Operators

**Directory**: `mutation_analysis/operators/`

**File**: `base.py` - Base infrastructure:
- **Mutation** dataclass: Records node, replacement, operator, visitor
- **MutationOperator**: Abstract base with visitor pattern over AST
- **AbstractUnaryOperatorDeletion**: Base for unary operator mutations

**Operator implementations**:

1. **arithmetic.py**: Arithmetic operator mutations
   - Addition ↔ Subtraction ↔ Multiplication ↔ Division
   - Floor division, modulo, power operator swaps
   - Unary plus/minus deletion

2. **logical.py**: Logical operator mutations
   - AND ↔ OR
   - Comparison operator substitutions (==, !=, <, >, <=, >=)
   - Boolean negation

3. **loop.py**: Loop control mutations
   - Break ↔ Continue
   - Loop condition modifications

4. **exception.py**: Exception handling mutations
   - Exception type swapping
   - Try/except block modifications

5. **inheritance.py**: Object-oriented mutations
   - Method override modifications
   - Super call mutations
   - Class hierarchy alterations

6. **decorator.py**: Decorator mutations
   - Decorator removal/substitution

7. **misc.py**: Miscellaneous mutations
   - Constant modifications
   - Statement deletions
   - Other edge cases

### Mutation Workflow

1. Parse SUT module to AST
2. Apply mutation operators to create mutants
3. Execute tests on each mutant
4. Track which assertions kill which mutants
5. Remove assertions that never violate on any mutant
6. Report mutation score: killed/(created - timeout)

## Integration Points

### Input Dependencies

- **Test Execution**: `pynguin.testcase.execution.TestCaseExecutor`
- **Test Structure**: `pynguin.testcase.testcase.TestCase`
- **Variable References**: `pynguin.testcase.variablereference`
- **Configuration**: `pynguin.configuration` for max test length, stale assertions

### Output Dependencies

- **Code Generation**: Assertions converted to AST for final test file output
- **Statistics**: Mutation metrics tracked via `pynguin.utils.statistics`
- **Test Chromosomes**: Assertions added to `TestCaseChromosome` and `TestSuiteChromosome`

## Configuration Options

- `test_case_output.allow_stale_assertions`: Whether to repeat unchanged assertions
- `test_case_output.max_length_test_case`: Maximum statements + assertions per test
- `subprocess`: Use subprocess for mutation execution (isolation)

## Workflow Summary

```
1. Execute test cases → capture runtime values
2. Generate assertions from traces
3. Filter flaky assertions (multiple runs)
4. [Optional] Apply mutation analysis:
   - Create mutants
   - Execute tests on mutants
   - Keep only assertions that detect mutants
5. Convert assertions to AST
6. Emit as test code
```

## Key Design Patterns

- **Visitor Pattern**: AssertionVisitor for extensible assertion processing
- **Observer Pattern**: Remote observers collect assertion data during execution
- **Strategy Pattern**: Multiple assertion generation strategies (basic, mutation, LLM)
- **Template Method**: Base generator with customizable mutation filtering

## Related Documentation

- Parent: [../AGENTS.md](../AGENTS.md) - Main Pynguin module overview
- [mutation_analysis/](mutation_analysis/) - Mutation testing subsystem (if sub-documentation exists)

---

*Generated: 2026-01-30*
*Module: pynguin.assertion*
