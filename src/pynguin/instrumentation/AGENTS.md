<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Instrumentation Module

<!-- Parent: ../AGENTS.md -->

**Purpose**: Code instrumentation system for coverage tracking and runtime analysis

**Critical for**: Measuring test effectiveness through branch/line coverage, dynamic constant seeding, type tracing, and checked coverage

---

## Overview

This directory contains Pynguin's bytecode instrumentation framework, which transforms Python code at runtime to enable:
- **Coverage measurement** (branch, line, checked)
- **Branch distance calculation** for fitness-guided test generation
- **Dynamic constant seeding** from runtime values
- **Type tracing** via ObjectProxy unwrapping
- **Execution trace collection** for test case slicing

The instrumentation operates via Python's import hook system, transforming modules as they're loaded.

---

## Core Architecture

### Import Hook Flow
```
Module Import
    ↓
InstrumentationFinder (meta path finder)
    ↓
InstrumentationLoader
    ↓
InstrumentationTransformer
    ↓
[Chain of InstrumentationAdapters]
    ↓
Instrumented Bytecode
```

### Adapter Chain Pattern
Uses a visitor chain pattern where each adapter can:
- Transform bytecode instructions
- Add tracer calls
- Maintain coverage tracking state
- Be conditionally applied based on coverage requirements

---

## Key Components

### 1. **machinery.py** - Import Machinery
**Core classes:**
- `InstrumentationFinder`: MetaPathFinder that intercepts module imports
- `InstrumentationLoader`: Loads and instruments the SUT (System Under Test)
- `TransitiveInstrumentationLoader`: Applies UnwrapTransformer to transitive imports
- `build_transformer()`: Factory for full instrumentation pipeline
- `build_transitive_transformer()`: Factory for lightweight transitive instrumentation

**Import filtering:**
- SUT gets full instrumentation (coverage + seeding + unwrapping)
- Transitive SUT imports get only UnwrapTransformer (prevents ObjectProxy leakage to C code)
- Stdlib and third-party packages are skipped

**Transitive import instrumentation**:
- Non-SUT modules imported during SUT loading receive UnwrapTransformer
- Prevents ObjectProxy from leaking to C-implemented operations

### 2. **transformer.py** - Bytecode Transformation Engine
**Core classes:**
- `InstrumentationTransformer`: Orchestrates adapter chain, traverses code objects recursively
- `InstrumentationAdapter`: Base class for visitor chain pattern
- `ModuleAstInfo` / `AstInfo`: AST metadata for coverage filtering (only_cover/no_cover lines)

**Adapter types:**
- `BranchCoverageInstrumentationAdapter`: Instruments predicates for branch distance
- `LineCoverageInstrumentationAdapter`: Instruments line execution tracking
- `CheckedCoverageInstrumentationAdapter`: Instruments for backward slice coverage
- `DynamicSeedingInstrumentationAdapter`: Extracts runtime constants
- `UnwrapTransformerInstrumentationAdapter`: Rewrites bytecode to unwrap ObjectProxy before C calls

**Key features:**
- `requires_coverage` property: Adapters can opt-out of coverage filtering
- `skip_ast_info`: Avoids circular imports for transitive instrumentation
- `skip_code_registration`: Prevents non-covered code from being registered
- Coverage filtering: `only_cover_lines` and `no_cover_lines` support

**Instrumentation chaining**:
```python
# Typical adapter chain for SUT
adapters = [
    BranchCoverageInstrumentation(subject_properties),
    LineCoverageInstrumentation(subject_properties),
    CheckedCoverageInstrumentation(subject_properties),
    DynamicSeedingInstrumentation(dynamic_constant_provider),
    UnwrapTransformerInstrumentation(),  # Python < 3.11 only
]
```

### 3. **tracer.py** - Execution Tracing
**Core classes:**
- `ExecutionTracer`: Collects branch distances, line visits, instruction traces
- `InstrumentationExecutionTracer`: Proxy for ExecutionTracer (enables tracer swapping)
- `ExecutionTrace`: Stores coverage data, branch distances, instruction sequences
- `SubjectProperties`: Registry of code objects, predicates, lines

**Trace data collected:**
- `executed_code_objects`: Set of executed code object IDs
- `executed_predicates`: Predicate execution counts
- `true_distances` / `false_distances`: Branch distance metrics
- `covered_line_ids`: Line coverage
- `executed_instructions`: Detailed instruction trace for slicing
- `executed_assertions`: Assertion positions in trace

**Distance functions:**
- Numeric: `abs(val1 - val2)` for equality, linear distances for comparisons
- Strings: Levenshtein distance variants for `==`, `<`, `<=`
- Containers: Minimum distance to any element for `in` operator
- Special: Identity (`is`/`is not`), exception matching

**Key optimization**: `_early_return` decorator aborts tracing when disabled or from wrong thread

### 4. **controlflow.py** - Control Flow Analysis
**Core classes:**
- `CFG`: Control-flow graph with artificial entry/exit nodes
- `BasicBlockNode`: Wrapper for bytecode BasicBlock with instrumentation support
- `ControlDependenceGraph`: Post-dominator tree-based CDG
- `ProgramGraph`: Base class using NetworkX DiGraph

**CFG construction:**
```python
CFG.from_bytecode(bytecode)
    ↓ Split try-begin blocks
    ↓ Create nodes and edges
    ↓ Insert ENTRY/EXIT artificial nodes
    ↓ Filter dead code nodes
```

**Special handling:**
- For-loop exit instrumentation via NOP nodes
- Yield nodes treated as exit points
- Infinite loops detected and marked as exits
- Try/except control flow

**Metrics:**
- `cyclomatic_complexity`: McCabe's complexity
- `diameter`: Graph diameter for distance metrics

### 5. **builtins_handler.py** - ObjectProxy Unwrapping
**Purpose**: Ensures C-implemented functions receive unwrapped objects, not ObjectProxy instances

**Core functionality:**
- `_needs_unwrapping()`: Detects if function is C-implemented or uninstrumented Python
- `_deep_unwrap()`: Recursively unwraps proxies in containers (tuple, list, dict, set)
- `unwrap_is()`: Handles `is` identity checks on proxies
- `unwrap_in()`: Handles `in` membership checks
- `call_with_unwrapped_tuple()`: Main call interception for CALL_FUNCTION
- `call_function_kw_tuple()`: Handles CALL_FUNCTION_KW
- `call_function_ex()`: Handles CALL_FUNCTION_EX

**Instrumentation decision tree:**
```
Is function a shim (isinstance/issubclass)?
  YES → Pass proxies (shimmed to record type checks)
  NO  → Check if Python function
        Is Python function?
          YES → Check if code.co_filename in instrumented_filenames
                Instrumented?
                  YES → Pass proxies (bytecode handles them)
                  NO  → Unwrap
          NO → Unwrap (C function)
```

**Type tracing integration:**
- Records builtin calls in `_self_usage_trace_node.called_builtins`
- Tracks which builtins were called on each proxy
- Labels: function name or `ClassName.method_name`

---

## Version-Specific Implementation (version/)

### Structure
- `__init__.py`: Dynamic import based on Python version (3.10-3.14)
- `common.py`: Shared protocols, enums, utilities
- `python3_10.py` through `python3_14.py`: Version-specific implementations

### Version-specific concerns
- **Opcode changes**: Stack effects, instruction names vary by version
- **New instructions**: Python 3.11+ has BINARY_OP, CACHE, etc.
- **Call conventions**: CALL_FUNCTION → CALL (3.11+)
- **Exception handling**: Try-block representation changed in 3.11

### Key protocols (common.py)
- `InstrumentationInstructionsGenerator`: Generates setup/call/teardown instruction sequences
- `StackEffectsFunction`: Calculates stack pops/pushes for opcodes
- `IsConditionalJumpFunction`: Identifies conditional jump instructions
- `GetBranchTypeFunction`: Extracts branch direction (true/false)

### Instrumentation setup actions
```python
class InstrumentationSetupAction(enum.IntEnum):
    NO_ACTION
    COPY_FIRST                      # DUP_TOP
    COPY_FIRST_SHIFT_DOWN_TWO       # DUP_TOP + ROT_THREE
    COPY_SECOND                     # DUP_TOP_TWO
    COPY_SECOND_SHIFT_DOWN_TWO
    COPY_SECOND_SHIFT_DOWN_THREE
    COPY_THIRD_SHIFT_DOWN_THREE
    COPY_THIRD_SHIFT_DOWN_FOUR
    COPY_FIRST_TWO
    ADD_FIRST_TWO
    ADD_FIRST_TWO_REVERSED
```

---

## Coverage Types

### 1. Branch Coverage
**Adapter**: `BranchCoverageInstrumentationAdapter`

**Instruments**:
- For-loops: Natural exit vs break/return
- Conditional jumps: if/while/for conditions
- Boolean predicates: `if x:` style
- Compare predicates: `if x > y:` style
- Exception matching: `except SomeError:` branches
- None-based jumps: Python 3.11+ optimization

**Distance calculation**:
- Numeric: Linear distance from threshold
- Strings: Edit distance variants
- Containers: Membership distance
- Booleans: Length/magnitude-based

### 2. Line Coverage
**Adapter**: `LineCoverageInstrumentationAdapter`

**Instruments**: First instruction of each line with tracer call

**Filtering**:
- Respects `only_cover_lines` and `no_cover_lines`
- Supports inline pragmas: `# pragma: no cover`, `# pynguin: no cover`

### 3. Checked Coverage
**Adapter**: `CheckedCoverageInstrumentationAdapter`

**Instruments**:
- Memory accesses (LOAD_FAST, STORE_FAST, LOAD_ATTR, etc.)
- Control flow (jumps, calls, returns)
- Attribute accesses
- Subscript accesses

**Purpose**: Backward slicing from assertions to determine relevant instructions

### 4. Dynamic Seeding
**Adapter**: `DynamicSeedingInstrumentationAdapter`

**Instruments**:
- Compare operations: Captures compared values
- String methods: `startswith()`, `endswith()`, `isalnum()`, etc.

**Purpose**: Seeds constant pool with values observed at runtime for better constant generation

---

## Instrumentation Flow Example

### Source Code
```python
def example(x):
    if x > 5:
        return "big"
    return "small"
```

### Instrumented Bytecode (conceptual)
```python
def example(x):
    # Line coverage
    __pynguin_tracer__.track_line_visit(line_id=1)

    # Branch coverage (x > 5)
    __pynguin_tracer__.executed_compare_predicate(
        x, 5, predicate_id=0, cmp_op=PynguinCompare.GT
    )
    if x > 5:
        # Line coverage
        __pynguin_tracer__.track_line_visit(line_id=2)
        return "big"

    # Line coverage
    __pynguin_tracer__.track_line_visit(line_id=3)
    return "small"
```

---

## Testing Considerations

### When modifying instrumentation:
1. **Test with SUT imports**: Ensure transitive imports work
2. **Test type tracing**: Verify ObjectProxy unwrapping
3. **Test coverage metrics**: Check branch/line coverage accuracy
4. **Test different Python versions**: Use version-specific tests
5. **Test with C extensions**: Ensure no ObjectProxy leakage
6. **Test assertion slicing**: Verify checked coverage traces

### Common gotchas:
- **Circular imports**: AST loading can trigger re-imports
- **Stack balance**: Instrumentation must preserve stack state
- **ObjectProxy leakage**: C functions cannot handle proxies
- **Thread safety**: ExecutionTracer uses thread-local state
- **Code object caching**: Same code object ID must not be instrumented twice

---

## Related Modules

- `../analyses/`: Static analysis used for determining what to instrument
- `../testcase/`: Uses execution traces for test case generation
- `../slicer/`: Backward slicing uses checked coverage traces
- `../utils/typetracing.py`: ObjectProxy implementation
- `../configuration.py`: Coverage metric configuration

---

## Key Design Patterns

### 1. Visitor Chain
Adapters form a chain where each can intercept and transform:
```python
adapter1.next_visitor = adapter2
adapter2.next_visitor = adapter3
adapter3.next_visitor = NullAdapter()
```

### 2. Proxy Pattern
`InstrumentationExecutionTracer` proxies `ExecutionTracer` to allow runtime swapping

### 3. Factory Pattern
`build_transformer()` and `build_transitive_transformer()` construct appropriate adapter chains

### 4. Template Method
`InstrumentationAdapter` defines visit_* template methods, subclasses override specific ones

---

## Performance Considerations

- **Import overhead**: Instrumentation adds 100-500ms per module
- **Runtime overhead**: 2-10x slowdown depending on coverage metrics
- **Memory overhead**: Trace data grows with execution length
- **Optimization**: Early return in tracer when disabled
- **Optimization**: Thread-local state to avoid lock contention
- **Optimization**: Only unwrap for C functions, not Python functions

---

## Future Work

- **Complete type tracing optimization**: Eliminate second execution entirely
- **Incremental instrumentation**: Only re-instrument changed code objects
- **Parallel instrumentation**: Speed up import of large codebases
- **Selective instrumentation**: More granular control over what gets instrumented
- **Better error messages**: When instrumentation fails, provide clearer diagnostics

---

**Updated**: 2026-01-30
