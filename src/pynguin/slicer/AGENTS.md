<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Slicer Module

<!-- Parent: ../AGENTS.md -->

The `slicer/` directory implements dynamic program slicing for checked coverage analysis, used to identify which statements are meaningfully checked by test assertions.

## Overview

This module performs dynamic program slicing to:
- Build execution flow graphs from test traces
- Compute backward slices from statement dependencies
- Identify statements checked by assertions
- Support checked coverage metrics

## Directory Structure

```
slicer/
├── dynamicslicer.py           # Main dynamic slicing engine
├── executedinstruction.py     # Executed instruction representation
├── executionflowbuilder.py    # Execution trace to control/data flow
├── statementslicingobserver.py # Observer for trace collection
└── stack/                      # Stack-based flow analysis
```

## Core Components

### 1. Dynamic Slicer (dynamicslicer.py)
- **DynamicSlicer**: Computes backward data/control flow slices
- Traces dependencies through variable assignments and control flow
- Identifies all statements influencing a given target statement
- Used for checked coverage computation

### 2. Execution Flow Builder (executionflowbuilder.py)
- **ExecutionFlowBuilder**: Converts execution traces to flow graphs
- Builds data dependence graph (variable definitions/uses)
- Builds control dependence graph (branch effects)
- Tracks program counter and statement dependencies

### 3. Executed Instruction (executedinstruction.py)
- **ExecutedInstruction**: Single executed bytecode instruction record
- Tracks variable state, stack state at execution point
- Links to source code line numbers
- Supports flow analysis

### 4. Slicing Observer (statementslicingobserver.py)
- **StatementSlicingObserver**: Collects execution traces for slicing
- Hooks into test execution to record bytecode instructions
- Builds execution history for post-hoc analysis
- Integrates with instrumentation system

### 5. Stack Module (stack/)
- Stack-based program analysis utilities
- Manages program counter and control flow
- Supports complex control structures

## Key Patterns

### Compute Slice for Statement
```python
from pynguin.slicer.dynamicslicer import DynamicSlicer

slicer = DynamicSlicer(execution_trace)
# Get all statements influencing the return value
slice_result = slicer.backward_slice(target_stmt)
influencing_stmts = slice_result.slice
```

### Checked Coverage
```python
# A statement is "checked" if:
# 1. An assertion reads from it (data dependence)
# 2. Control flow depends on it (control dependence)
# 3. Return value flows to assertion

# Via ga/computations.py:
# compute_assertion_checked_coverage() uses DynamicSlicer
```

## Algorithm Overview

### Backward Slicing
1. Start with target statement (e.g., return value)
2. Trace backward through data dependencies:
   - Variable uses → definitions
   - Function returns → call arguments
3. Trace backward through control dependencies:
   - Conditional branches affecting execution
   - Loop conditions
4. Collect all statements in the slice

### Execution Flow Graph Construction
1. Parse execution trace (sequence of instructions)
2. Build data flow edges (definitions → uses)
3. Build control flow edges (branches)
4. Annotate with variable values at each point

## Integration Points

### With GA Module
- **CheckedCoverageGoal**: Uses DynamicSlicer to identify checked statements
- **compute_assertion_checked_coverage()**: Calls slicer for each assertion
- Fitness functions use slice results to guide search

### With Instrumentation
- **StatementSlicingObserver**: Integrated into execution trace collection
- Works with bytecode instrumentation for execution monitoring
- Complements branch distance computation

### With Test Case
- **TestCase.get_slicing_trace()**: Provides execution trace
- Test cases cache execution results for slicing
- Multiple tests can share slicer for efficiency

## Coverage Computation

Checked coverage identifies statements that:
1. **Directly checked**: Appear in assertion condition
2. **Data dependent**: Their values flow to assertion
3. **Control dependent**: Their branching affects assertion execution

Example:
```python
x = process(data)  # Statement A
if x > 0:          # Statement B - control flow
    assert x == expected  # Assertion reads x (data dependent)

# Slice for assertion: {Statement A, Statement B}
```

## Performance Considerations

- **Lazy slicing**: Slices computed on-demand for each assertion
- **Trace caching**: Execution traces stored during test run
- **Incremental updates**: Reuse previous slices for similar tests
- **Memory efficiency**: Stream-based trace building

## Related Modules

- `ga/` - Uses checked coverage from slicing results
- `instrumentation/` - Provides execution trace collection
- `testcase/` - Test cases provide execution traces
- `analyses/` - Complements static analysis with dynamic information

## Key Files to Explore

- `dynamicslicer.py` - Core backward slicing algorithm
- `executionflowbuilder.py` - Trace to graph conversion
- `executedinstruction.py` - Instruction representation

---

**Timestamp**: 2026-01-30
