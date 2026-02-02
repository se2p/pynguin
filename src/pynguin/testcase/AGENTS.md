<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# testcase/

<!-- Parent: ../AGENTS.md -->

**Purpose**: Internal representation of generated tests - the core model for test cases, statements, and execution.

**Last Updated**: 2026-01-30

## Overview

This directory contains the complete internal model for representing test cases in Pynguin. It defines the abstract syntax tree (AST) for test cases composed of statements that manipulate variables, and provides execution and export capabilities to convert these internal representations into executable pytest code.

## Key Components

### Core Models

#### Statement Types (`statement.py`)
The fundamental building blocks of test cases. All statements inherit from the abstract `Statement` base class.

**Primitive Statements**:
- `IntPrimitiveStatement`, `UIntPrimitiveStatement` - Integer values
- `FloatPrimitiveStatement` - Floating-point values
- `ComplexPrimitiveStatement` - Complex numbers
- `StringPrimitiveStatement` - String values with multiple implementations:
  - `RandomStringPrimitiveStatement` - Random strings
  - `FakerStringPrimitiveStatement` - Faker-generated strings
  - `FandangoStringPrimitiveStatement` - Grammar-based strings
  - `FandangoFakerStringPrimitiveStatement` - Combined grammar+faker
- `BytesPrimitiveStatement` - Byte sequences
- `BooleanPrimitiveStatement` - Boolean values
- `EnumPrimitiveStatement` - Enum values
- `ClassPrimitiveStatement` - Class references
- `NoneStatement` - None value

**Collection Statements**:
- `ListStatement` - List collections
- `SetStatement` - Set collections
- `TupleStatement` - Tuple collections
- `DictStatement` - Dictionary collections
- `NdArrayStatement` - NumPy array collections

**Call Statements**:
- `ConstructorStatement` - Object instantiation
- `MethodStatement` - Method calls on objects
- `FunctionStatement` - Function calls
- `FieldStatement` - Field access/assignment
- `AssignmentStatement` - Variable assignment

**Base Classes**:
- `Statement` - Abstract base for all statements
- `VariableCreatingStatement` - Statements that create variables (have return values)
- `ParametrizedStatement` - Statements with parameters (constructors, methods, functions)
- `CollectionStatement` - Base for collection types
- `PrimitiveStatement[T]` - Generic base for primitive types

#### Test Cases (`testcase.py`, `defaulttestcase.py`)

**`TestCase` (Abstract Base)**:
- Interface for test case implementations
- Manages ordered list of statements
- Provides dependency tracking between variables
- Supports cloning, mutation, and structural comparison

**Key Operations**:
- `add_statement()` - Add statement at position
- `remove()` - Remove statement by position
- `remove_with_forward_dependencies()` - Remove statement and dependents
- `get_objects()` - Find variables of specific type
- `get_dependencies()` - Get backward dependencies
- `get_forward_dependencies()` - Get forward dependencies
- `clone()` - Deep copy with optional limit

#### Variable References (`variablereference.py`)

**Reference Hierarchy**:
- `Reference` - Abstract base for anything referenceable
- `VariableReference` - Reference to variables in test case
- `CallBasedVariableReference` - Variable with dynamically updated type
- `FieldReference` - Reference to instance fields
- `StaticFieldReference` - Reference to static class fields
- `StaticModuleFieldReference` - Reference to module-level fields

**Key Concepts**:
- Variables identified by object identity (no eq/hash)
- Distance metric for mutation selection
- Structural equality for test case comparison
- Type information tracked per reference

### Visitors

#### Statement Visitor (`statement.py`)
Abstract visitor pattern for processing statements:
- Visit methods for each statement type
- Used by export, mutation, and analysis

#### Test Case Visitor (`testcasevisitor.py`)
Visitor pattern for test case implementations:
- `visit_default_test_case()` - Process test cases

### Execution Model (`execution.py`)

**`ExecutionContext`**:
- Maintains execution state (local/global namespaces)
- Variable name management
- Module alias management
- Converts statements to executable AST nodes

**Execution Observers**:
- `RemoteExecutionObserver` - Base for execution observation
- Thread-local state for concurrent execution
- Hooks for before/after test execution

**Key Features**:
- Converts internal representation to AST
- Manages variable/module namespaces
- Supports remote execution with observers
- Handles assertions alongside statements

### Export System (`export.py`, `statement_to_ast.py`, `testcase_to_ast.py`)

**Export Pipeline**:
1. `PyTestChromosomeToAstVisitor` - Visit chromosomes containing test cases
2. `TestCaseToAstVisitor` - Convert test case to AST
3. `StatementToAstVisitor` - Convert individual statements to AST nodes
4. Generate pytest-compatible Python code

**Key Features**:
- Module import management with aliases
- Canonical module name resolution
- Pytest function generation
- Support for failing tests (exception assertions)

### Local Search & Optimization

**Local Search Components**:
- `localsearch.py` - Local search strategies
- `localsearchstatement.py` - Statement-level local search
- `localsearchtimer.py` - Timing control
- `localsearchobjective.py` - Objective functions
- `llmlocalsearch.py` - LLM-assisted local search

### Test Factory

**`testfactory.py`**:
- Factory for creating statements
- Handles type-aware statement generation
- Manages test cluster integration

## Architecture Patterns

### Statement Lifecycle

1. **Creation**: Factory creates typed statement
2. **Reference**: Statement gets `VariableReference` (if variable-creating)
3. **Addition**: Statement added to test case
4. **Execution**: Context converts to AST and executes
5. **Export**: Statement converted to pytest code

### Variable Dependencies

```
var_0 = Constructor()      # No dependencies
var_1 = var_0.method()     # Depends on var_0
var_2 = function(var_1)    # Depends on var_1 (transitively on var_0)
```

- Forward dependencies: var_0 → {var_1} → {var_2}
- Backward dependencies: var_2 → {var_1} → {var_0}

### Mutation Operations

Statements support mutation through:
- `mutate()` - Mutate statement content
- `replace()` - Replace variable references
- Delta debugging for minimization

### Structural Equality

Test cases use structural equality (not object identity):
- `structural_eq()` - Compare statement structure
- `structural_hash()` - Hash statement structure
- Memo maps variables between test cases

## Key Abstractions

### Statement → AST Conversion

Each statement type implements:
- `accept(visitor)` - Visitor pattern entry point
- Visitor creates corresponding `ast.stmt` node
- Handles variable naming, module aliasing

### Execution Context

Manages runtime state:
- **Local namespace**: Variables created during execution
- **Global namespace**: Imported modules
- **Variable names**: Variable reference → name mapping
- **Module aliases**: Module → alias mapping

### Reference System

Variables are references, not values:
- `VariableReference` = handle to variable in test case
- References have types (from type inference)
- Types can be updated dynamically (`CallBasedVariableReference`)
- References support attribute access (`FieldReference`)

## Dependencies

**Internal**:
- `../assertion/` - Assertion generation and checking
- `../analyses/` - Type system, test cluster
- `../instrumentation/` - Code instrumentation for execution
- `../ga/` - Genetic algorithm chromosomes
- `../utils/` - Naming, randomness, type utilities

**External**:
- `ast` - Python AST manipulation
- `pytest` - Test execution framework
- `faker` - String generation (optional)
- `numpy` - Array support (optional)
- `multiprocess` - Parallel execution

## Common Operations

### Creating a Test Case
```python
test_case = DefaultTestCase(test_cluster)
stmt = IntPrimitiveStatement(test_case, 42)
var_ref = test_case.add_statement(stmt)
```

### Cloning with Modifications
```python
cloned = test_case.clone(limit=5)  # Clone first 5 statements
cloned.chop(3)  # Remove statements after position 3
```

### Finding Variables
```python
# Find all variables of type 'int' before position 10
int_vars = test_case.get_objects(IntType(), position=10)
```

### Exporting to Code
```python
visitor = PyTestChromosomeToAstVisitor()
chromosome.accept(visitor)
# visitor.module_aliases contains imports
# visitor.conversion_results contains AST
```

## Testing

This module is tested extensively through:
- Unit tests for statement types
- Integration tests for execution
- Export tests for AST generation
- Mutation tests for genetic operations

## Related Documentation

- Statement creation: See `testfactory.py`
- Execution: See `execution.py`, `../instrumentation/`
- Export: See `export.py`, `statement_to_ast.py`
- Assertions: See `../assertion/AGENTS.md`
- Type system: See `../analyses/typesystem.py`
