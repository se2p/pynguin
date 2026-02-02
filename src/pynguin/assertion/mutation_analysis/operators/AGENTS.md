<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Mutation Operators Module

<!-- Parent: ../AGENTS.md -->

**Purpose**: Provides AST-based mutation operators that transform code to create mutants for testing assertion quality.

## Overview

This module implements mutation operators—reusable AST transformations that modify code semantics to create mutants. Each operator targets specific language constructs (arithmetic operators, comparisons, loops, etc.) and generates alternative versions that tests should detect.

## Key Components

### Base Infrastructure

**File**: `base.py`

Core mutation framework:

- **Mutation** (dataclass): Immutable record of a mutation
  - `node`: Original AST node being mutated
  - `replacement`: New AST node replacing the original
  - `operator`: Which operator created this mutation
  - `visitor`: Visitor instance (for traversal state)

- **MutationOperator** (abstract base):
  - Visitor pattern over AST nodes
  - Abstract `visit_*` methods for each AST node type to override
  - Generates mutations by yielding (original, replacement, operator) tuples
  - Tracks visited nodes to avoid infinite recursion

- **AbstractUnaryOperatorDeletion**: Helper for unary operator mutations
  - Removes unary +/- from expressions
  - Returns expression without the operator

- **fix_lineno()**: Utility to copy line numbers between AST nodes

### Arithmetic Operators

**File**: `arithmetic.py` - **ArithmeticOperatorDeletion**, **ArithmeticOperatorReplacement**

Mutations on binary arithmetic operations:

- Binary operators: `+`, `-`, `*`, `/`, `//`, `%`, `**`
- Swaps: Addition ↔ Subtraction, Multiplication ↔ Division, etc.
- Unary mutations: Removes unary `+` and `-`
- Examples: `a + b` → `a - b`, `a * b` → `a / b`

### Logical Operators

**File**: `logical.py` - **BooleanReplacement**, **ComparisonOperatorReplacement**

Mutations on boolean logic and comparisons:

- Boolean operators: `and` ↔ `or`
- Comparison operators: `==`, `!=`, `<`, `>`, `<=`, `>=` substitutions
- Negation: Adds/removes `not` operators
- Examples: `a and b` → `a or b`, `a < b` → `a <= b`

### Loop Control

**File**: `loop.py` - **BreakContinueReplacement**

Mutations on loop control flow:

- Swaps `break` ↔ `continue` statements
- Modifies loop conditions
- Examples: `break` → `continue`, condition changes

### Exception Handling

**File**: `exception.py` - **ExceptionHandler**, **TryExcept**

Mutations on exception handling constructs:

- Exception type swapping in except clauses
- Try/except block modifications
- Exception matching changes
- Examples: `except ValueError` → `except TypeError`

### Inheritance and Object-Oriented

**File**: `inheritance.py` - **SuperCalling**, **SelfCalling**

Mutations on OO constructs:

- `super()` call mutations
- Method override modifications
- Class hierarchy alterations
- Self reference changes

### Decorators

**File**: `decorator.py` - **DecoratorRemoval**, **DecoratorSubstitution**

Mutations on decorator applications:

- Removes function/class decorators
- Substitutes similar decorators
- Modifies decorator arguments

### Miscellaneous

**File**: `misc.py` - Various edge cases:

- Constant value modifications
- Statement deletions
- String literal mutations
- Collection initialization changes

## Mutation Generation Workflow

```
1. Parse SUT to AST
2. Create mutation operator instance
3. Visit root node, which recursively visits children
4. Each visit method:
   - Identifies mutation opportunities in current node
   - Yields (original, replacement, operator) for each mutation
   - Calls super().generic_visit() to continue traversal
5. Controller collects all mutations
6. Apply each mutation to create mutant
```

## Integration Points

### Input Dependencies

- **AST Nodes**: Python ast module
- **Parent Controller**: `pynguin.assertion.mutation_analysis.controller.MutationController`
- **Parent Strategies**: `pynguin.assertion.mutation_analysis.strategies.*HOMStrategy`

### Output Dependencies

- **Mutant Execution**: Each mutation applied to create a mutated module
- **Mutation Metrics**: Mutations tracked for coverage and filtering

## Key Design Patterns

- **Visitor Pattern**: Extensible AST traversal with visit_* methods
- **Generator Pattern**: Yields mutations lazily for memory efficiency
- **Immutable Records**: Mutation dataclass captures immutable change info
- **Node Copying**: Uses copy.deepcopy() to safely create replacement nodes

## Extension Points

To add new mutation operators:

1. Create file: `newoperator.py`
2. Extend `MutationOperator` base class
3. Override `visit_*` methods for target AST nodes
4. Yield `Mutation(node, replacement, self)` tuples
5. Register in `__init__.py` to make available to MutationController

## Related Documentation

- Parent: [../AGENTS.md](../AGENTS.md) - Mutation analysis subsystem
- [arithmetic.py](arithmetic.py) - Arithmetic operator mutations
- [logical.py](logical.py) - Logical operator mutations
- [loop.py](loop.py) - Loop control mutations
- [exception.py](exception.py) - Exception handling mutations
- [inheritance.py](inheritance.py) - OO mutations
- [decorator.py](decorator.py) - Decorator mutations
- [misc.py](misc.py) - Miscellaneous mutations

---

*Generated: 2026-01-30*
*Module: pynguin.assertion.mutation_analysis.operators*
