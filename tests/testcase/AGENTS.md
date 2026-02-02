<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Test Case Representation Tests

**Parent:** `../AGENTS.md`

Test suite for pynguin's test case representation, statements, execution, and manipulation.

## Directory Structure

### Core Test Case Components

- **`test_testcase.py`** - Basic test case representation
  - Test case creation and structure
  - Statement management
  - Test case lifecycle
  - Assertion management

- **`test_statementlist.py`** - Statement list container
  - Managing ordered statement sequences
  - Statement insertion and removal
  - Reference tracking
  - Statement indexing

- **`test_statement.py`** - Statement base class
  - Core statement interface
  - Execution semantics
  - Return value tracking
  - Exception handling

### Statement Types

- **`test_statements.py`** - All statement implementations
  - Variable assignments
  - Function calls
  - Method invocations
  - Object creation
  - Primitive literals
  - Collection construction
  - Type casting
  - File size: Comprehensive (main statement test file)

- **`test_primitivestatements.py`** - Primitive value statements
  - Boolean, integer, float, string literals
  - None values
  - Collection literals (lists, dicts, sets)

- **`test_functionstatement.py`** - Function call statements
  - Calling module-level functions
  - Function reference handling
  - Argument passing
  - Return value handling

- **`test_methodstatement.py`** - Method invocation statements
  - Instance method calls
  - Class method calls
  - Static method calls
  - Method reference resolution

- **`test_assignmentstatement.py`** - Assignment statements
  - Variable assignment
  - Reference updating
  - Type tracking
  - Side effect handling

### Test Case Utilities

- **`test_executionresult.py`** - Execution result representation
  - Test execution output
  - Exception information
  - Coverage results
  - Execution time tracking

- **`test_testcaseclone.py`** - Test case cloning
  - Deep copying test cases
  - Statement deep copying
  - Reference preservation
  - Mutation from clone

- **`test_defaultTestcase.py`** - Default test case implementation
  - Standard test case factory
  - Configuration handling
  - Default statement creation
  - Standard behavior verification

### Advanced Features

- **`test_generics.py`** - Generic type handling
  - Generic class instantiation
  - Type parameter tracking
  - Generic method calls
  - Type variable substitution

- **`test_random.py`** - Randomization in test cases
  - Random primitive value generation
  - Random statement generation
  - Seeded randomness for reproducibility
  - Random mutation operations

- **`test_coverage.py`** - Coverage tracking
  - Coverage goal tracking per statement
  - Coverage analysis
  - Goal identification
  - Coverage metrics

- **`test_variablereference.py`** - Variable reference management
  - Reference counting
  - Scope management
  - Definition tracking
  - Use-def chains

- **`test_assertions.py`** - Assertion statements
  - Assertion creation
  - Expected value representation
  - Assertion validation
  - Assertion generation

## Test Organization

### By Concern

| Concern | Test Modules | Purpose |
|---------|-------------|---------|
| Test Case Structure | `test_testcase.py`, `test_statementlist.py` | Container and lifecycle |
| Statement Types | `test_statements.py`, `test_primitivestatements.py` | Various statement kinds |
| Execution | `test_executionresult.py`, `test_statement.py` | Running and results |
| Operations | `test_testcaseclone.py`, `test_random.py` | Cloning and mutation |
| Type System | `test_generics.py`, `test_variablereference.py` | Type tracking |
| Coverage | `test_coverage.py` | Coverage analysis |
| Assertions | `test_assertions.py` | Assertion handling |
| Factories | `test_defaultTestcase.py` | Test case creation |

### Statistics

- **Total Test Files:** 34 Python files
- **Total Size:** Comprehensive test case subsystem coverage
- **Test Methods:** 100+ individual test functions

## Key Testing Areas

1. **Test Case Representation**
   - Test case structure and composition
   - Statement sequence management
   - Reference integrity
   - Lifecycle management

2. **Statement Types**
   - Creating different statement kinds
   - Type-specific behavior
   - Argument handling
   - Return value tracking

3. **Test Execution**
   - Interpreting statements
   - Tracking execution results
   - Exception handling
   - Coverage collection

4. **Mutation Operations**
   - Cloning test cases
   - Statement mutation
   - Reference updating after mutation
   - Type preservation

5. **Type System**
   - Generic type handling
   - Type parameter tracking
   - Variable reference types
   - Type variable substitution

6. **Coverage Integration**
   - Coverage goal tracking
   - Coverage per statement
   - Coverage aggregation
   - Goal identification

7. **Assertion Handling**
   - Assertion statement creation
   - Expected value representation
   - Assertion validation
   - False positive handling

## Test Case Execution Model

Tests verify the execution model:

1. **Creation Phase**
   - Build statement sequence
   - Establish variable references
   - Type annotation

2. **Execution Phase**
   - Interpret statements sequentially
   - Track variable values
   - Collect coverage
   - Record exceptions

3. **Result Phase**
   - Capture execution results
   - Determine test outcome
   - Analyze coverage
   - Verify assertions

## Integration Points

Test case tests verify integration with:
- **GA System** - Mutating test cases during evolution
- **Instrumentation** - Coverage collection during execution
- **Assertion Generation** - Assertion creation and insertion
- **Type System** - Type tracking and inference
- **Execution Engine** - Running instrumented code

## Mutation Operators

Tests verify test case mutation:
- **Statement Addition** - Adding new statements
- **Statement Deletion** - Removing statements
- **Statement Replacement** - Changing statement behavior
- **Argument Mutation** - Modifying statement arguments
- **Reference Updates** - Maintaining reference consistency

## Reference Semantics

Tests verify reference handling:
- **Variable Definition** - Tracking variable origin
- **Variable Usage** - Using defined variables
- **Reference Consistency** - Maintaining reference validity
- **Dead Code Removal** - Identifying unused definitions
- **Use-Def Chains** - Tracking data flow

See individual test files for specific test case semantics.
