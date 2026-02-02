<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Mutation Analysis Subsystem

<!-- Parent: ../AGENTS.md -->

**Purpose**: Implements mutation testing to measure assertion quality and filter assertions based on their ability to detect code mutations.

## Overview

The mutation analysis subsystem creates controlled mutants of the System Under Test (SUT), executes test assertions against these mutants, and removes assertions that fail to detect any mutations. This ensures generated assertions are meaningful and catch real code defects.

## Architecture

### Orchestration

**File**: `controller.py` - **MutationController**

Central orchestration for the mutation testing workflow:

- **`create_mutants(module, operators)`**: Yields (mutated_module, mutations) pairs
- **`execute_mutations(tests, mutants)`**: Runs test suite against each mutant variant
- **`track_mutation_score(killed, created, timeout)`**: Reports metrics (killed/(created - timeout))
- **Error handling**: Gracefully skips invalid mutants and continues execution

### Higher-Order Mutation (HOM)

**File**: `strategies.py` - Mutation combination strategies

Multiple mutations applied per mutant (reduces test execution overhead):

1. **FirstToLastHOMStrategy**: Combines first and last mutations in sequence
2. **EachChoiceHOMStrategy**: Sequentially applies each mutation
3. **BetweenOperatorsHOMStrategy**: Ensures diverse operator coverage across mutations
4. **RandomHOMStrategy**: Random selection of mutation combinations

**Benefits**: Fewer mutants to test while maintaining operator diversity

## Mutation Operators

**Directory**: `operators/`

Comprehensive set of AST-level mutation operators organized by category.

### Base Infrastructure

**File**: `base.py`

- **Mutation** dataclass: Records (node, replacement, operator, visitor) for each mutation
- **MutationOperator**: Abstract base class with visitor pattern over AST nodes
  - Subclasses implement `visit_NodeType()` methods to find and mutate specific AST node types
  - Supports both single mutations and higher-order combinations
- **AbstractUnaryOperatorDeletion**: Base for unary operator removal mutations (e.g., unary minus, logical not)

### Arithmetic Operators

**File**: `arithmetic.py` - **ArithmeticOperatorMutation**

Mutations on arithmetic operators:

- **Binary swaps**:
  - Addition (Add) ↔ Subtraction (Sub)
  - Multiplication (Mult) ↔ Division (Div)
  - Floor division (FloorDiv) ↔ Modulo (Mod)
  - Power (Pow) ↔ other operators
- **Unary operator deletion**:
  - Unary Plus (UAdd) deletion
  - Unary Minus (USub) deletion

**Examples**:
```python
a + b  →  a - b
a * b  →  a / b
-x     →  x
```

### Logical Operators

**File**: `logical.py` - **LogicalOperatorMutation**

Mutations on logical and comparison operators:

- **Logical binary swaps**:
  - AND (BoolOp with And()) ↔ OR (BoolOp with Or())
- **Comparison operator swaps**:
  - Equality (Eq) ↔ Inequality (NotEq)
  - Less than (Lt) ↔ Greater than (Gt)
  - Less-equal (LtE) ↔ Greater-equal (GtE)
  - Membership tests (In) ↔ (NotIn)
  - Identity checks (Is) ↔ (IsNot)
- **Boolean negation**:
  - Remove logical not (UnaryOp with Not())

**Examples**:
```python
a and b      →  a or b
a == b       →  a != b
a < b        →  a > b
a is None    →  a is not None
not x        →  x
```

### Loop Control

**File**: `loop.py` - **LoopMutation**

Mutations on loop constructs:

- **Break ↔ Continue**: Swap statement types in loops
- **Loop condition modifications**: Remove or negate loop conditions
- **For/While loop alterations**: Change loop behavior

**Examples**:
```python
while condition:
    break  →  continue
```

### Exception Handling

**File**: `exception.py` - **ExceptionMutation**

Mutations on exception handling:

- **Exception type swapping**: Replace caught exception with different types
- **Try/except block modifications**: Remove exception handlers
- **Raise statement mutations**: Modify exception raising

**Examples**:
```python
except ValueError:  →  except TypeError:
raise e             →  pass
```

### Inheritance & OOP

**File**: `inheritance.py` - **InheritanceMutation**

Mutations on object-oriented constructs:

- **Method override modifications**: Change method implementations
- **Super call mutations**: Remove or modify super() calls
- **Class hierarchy alterations**: Change base classes
- **Method attribute access**: Modify self/class references

**Examples**:
```python
super().method()  →  pass
class Child(Parent):  →  class Child(Other):
```

### Decorator Mutations

**File**: `decorator.py` - **DecoratorMutation**

Mutations on decorators:

- **Decorator removal**: Delete decorators from functions/classes
- **Decorator substitution**: Replace with dummy decorators
- **Decorator order changes**: Reorder multiple decorators

**Examples**:
```python
@cache
def func():  →  def func():

@decorator1
@decorator2  →  @decorator2
             →  @decorator1
```

### Miscellaneous Mutations

**File**: `misc.py` - **MiscellaneousMutation**

Edge cases and other mutations:

- **Constant modifications**: Change numeric/string literals
- **Statement deletions**: Remove pass, return, etc.
- **Variable assignments**: Modify assignment targets/values
- **Function call argument mutations**: Change call arguments

**Examples**:
```python
x = 42    →  x = 43
return x  →  return None
```

## Mutation Workflow

### Typical Execution Flow

1. **Parse SUT**: Load module to AST
2. **Select Operators**: Choose mutation operators to apply
3. **Generate Mutants**:
   - For each AST node matching operator patterns
   - Apply mutation using selected HOM strategy
   - Yield (mutated_module, mutations_list) pairs
4. **Execute Tests**:
   - For each mutant, execute test assertions
   - Track which assertions fail (kill the mutant)
5. **Measure Coverage**:
   - Count assertions that killed at least one mutant
   - Remove assertions with zero kills
   - Calculate mutation score: killed/(created - timeout)
6. **Report Results**: Mutation metrics and statistics

### Integration with Assertion Generation

**File**: `../assertiongenerator.py` - **MutationAnalysisAssertionGenerator**

- Extends base AssertionGenerator with mutation filtering
- After generating assertions from test execution traces:
  1. Create mutants of the SUT
  2. Run generated test suite against each mutant
  3. Identify assertions that detect mutations
  4. Remove assertions that never cause failures
- **Output**: High-quality assertion set with documented mutation score

## Data Flow

```
Source Code (SUT)
    ↓
[Parse to AST]
    ↓
[MutationController]
    ├─→ [ArithmeticOperator] → mutations
    ├─→ [LogicalOperator] → mutations
    ├─→ [LoopMutation] → mutations
    └─→ [HOM Strategy] → combined mutations
    ↓
[Generate Mutant Variants]
    ↓
[Execute Tests Against Mutants]
    ↓
[Track Killed Mutants]
    ↓
[Filter Low-Impact Assertions]
    ↓
[Mutation Score Report]
```

## Operator Reference Table

| Operator Class | File | Mutations | Count |
|---|---|---|---|
| ArithmeticOperatorMutation | arithmetic.py | +↔-↔*, /↔//, %↔**, unary +/- | ~12 |
| LogicalOperatorMutation | logical.py | and↔or, ==↔!=, <↔>, ≤↔≥, in↔not in, is↔is not, not removal | ~14 |
| LoopMutation | loop.py | break↔continue, condition mods | ~3 |
| ExceptionMutation | exception.py | Exception type swaps, handler removal | ~5 |
| InheritanceMutation | inheritance.py | super() mods, base class changes | ~4 |
| DecoratorMutation | decorator.py | Decorator removal/substitution | ~2 |
| MiscellaneousMutation | misc.py | Constant mods, statement deletion | ~6 |

## Configuration & Tuning

### Parameters

- **`mutation_operators`**: List of operator classes to apply
- **`hom_strategy`**: Higher-order mutation strategy (FirstToLast, EachChoice, etc.)
- **`max_mutants`**: Limit total mutants to evaluate (optional)
- **`timeout_per_mutant`**: Execution timeout per mutant variant

### Performance Considerations

- **HOM Strategy**: Reduces mutant count; trade-off between coverage and speed
- **Operator Selection**: Disable expensive operators for quick iteration
- **Timeout Handling**: Count timeouts separately (excluded from denominator)

## Key Design Patterns

- **Visitor Pattern**: MutationOperator subclasses visit AST nodes
- **Strategy Pattern**: HOM strategies for different mutation combination approaches
- **Generator Pattern**: MutationController yields mutants on-demand (lazy evaluation)
- **Data Class**: Mutation dataclass for immutable mutation records

## Related Documentation

- Parent: [../AGENTS.md](../AGENTS.md) - Assertion generation module overview
- Sibling: [../../AGENTS.md](../../AGENTS.md) - Testcase module overview
- Root: [../../../../AGENTS.md](../../../../AGENTS.md) - Pynguin main overview

---

*Generated: 2026-01-30*
*Module: pynguin.assertion.mutation_analysis*
