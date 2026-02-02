<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Instrumentation Tests

**Parent:** `../AGENTS.md`

Test suite for pynguin's bytecode instrumentation and code transformation system, including coverage tracking, type tracing, and code modification.

## Directory Structure

### Core Instrumentation Tests

- **`test_integrationinstrumenter.py`** - Full instrumentation pipeline
  - End-to-end instrumentation workflow
  - Module loading and transformation
  - Coverage tracking integration

- **`test_instrumeter.py`** - Main instrumentation engine
  - Bytecode manipulation
  - Hook injection
  - Code transformation verification

- **`test_transformers.py`** - AST/bytecode transformers
  - Individual transformer implementations
  - Coverage tracking transformations
  - Type tracing transformations

### Specialized Transformations

- **`test_bytecode_modifiers.py`** - Bytecode-level modifications
  - Direct bytecode instruction modification
  - Hook point injection
  - Instruction sequence optimization

- **`test_coverage_hooks.py`** - Coverage tracking hooks
  - Line coverage tracking
  - Branch coverage tracking
  - Exception coverage tracking

- **`test_type_tracing_hooks.py`** - Type inference hooks
  - Runtime type collection
  - Type annotation validation
  - Generic type parameter tracking

- **`test_ast_transformers.py`** - AST-level transformations
  - Abstract syntax tree modification
  - Pattern-based code rewriting
  - Source-to-source transformations

- **`test_code_analysis.py`** - Code structure analysis
  - Program structure extraction
  - Dependency analysis
  - Reachability computation

### Integration Components

- **`test_module_loader.py`** - Dynamic module loading
  - Instrumented module import
  - sys.meta_path integration
  - Import hook management

- **`test_shim_context.py`** - Shim context manager
  - Runtime context for instrumentation
  - State management during execution
  - Cleanup and restoration

### Fixture Support

- **`fixtures/instrumentation/`** (sibling directory)
  - Target modules for instrumentation testing
  - 13 test fixture modules
  - Real code to instrument and analyze

## Test Organization

### By Feature

| Feature | Test Module | Purpose |
|---------|-------------|---------|
| Coverage Tracking | `test_coverage_hooks.py` | Line/branch/exception coverage |
| Type Tracing | `test_type_tracing_hooks.py` | Runtime type information |
| Code Analysis | `test_code_analysis.py` | Structure and dependencies |
| AST Transform | `test_ast_transformers.py` | AST-level code modification |
| Bytecode Modify | `test_bytecode_modifiers.py` | Bytecode-level changes |
| Module Loading | `test_module_loader.py` | Dynamic import and loading |
| Integration | `test_integrationinstrumenter.py` | Full pipeline |
| Main Engine | `test_instrumeter.py` | Core instrumentation |
| Transformers | `test_transformers.py` | Transformer implementations |
| Context | `test_shim_context.py` | Execution context |

### Statistics

- **Total Test Files:** 9 Python files
- **Total Size:** Comprehensive coverage module
- **Fixture Count:** 13 instrumentation fixtures

## Key Testing Areas

1. **Coverage Tracking**
   - Injecting line coverage tracking
   - Branch coverage condition tracking
   - Exception coverage hooks
   - Coverage data collection

2. **Type Tracing**
   - Runtime type annotation validation
   - Generic type parameter tracking
   - Variable type recording
   - Type inference assistance

3. **Code Transformation**
   - AST-level code modification
   - Bytecode instruction injection
   - Hook point identification
   - Instrumentation point selection

4. **Module Loading**
   - Custom import hooks
   - Module instrumentation during import
   - Caching instrumented bytecode
   - sys.meta_path integration

5. **Context Management**
   - Instrumentation state isolation
   - Thread-safe context
   - Cleanup on context exit
   - Nested context handling

## Instrumentation Phases

Tests verify transformation pipeline:

1. **Source Analysis** (`test_code_analysis.py`)
   - Extract program structure
   - Identify instrumentation points
   - Compute reachability

2. **AST Transformation** (`test_ast_transformers.py`)
   - Modify abstract syntax tree
   - Insert tracking code
   - Preserve semantics

3. **Bytecode Generation** (implicit)
   - Compile modified AST
   - Verify bytecode correctness
   - Optimize code

4. **Hook Injection** (`test_bytecode_modifiers.py`)
   - Insert runtime hooks
   - Connect to tracking system
   - Validate hook points

5. **Module Loading** (`test_module_loader.py`)
   - Load instrumented module
   - Initialize tracking state
   - Manage dependencies

## Integration Points

Instrumentation tests verify integration with:
- **Coverage System** - Tracking coverage during execution
- **Type Tracing System** - Collecting runtime types
- **Test Case Execution** - Running instrumented code
- **Test Generation** - Using coverage feedback in GA
- **Assertion Generation** - Type information for assertions

## Fixtures Usage

Target fixture modules in `fixtures/instrumentation/`:
- Simple modules for basic instrumentation
- Complex modules for realistic scenarios
- Edge cases and error conditions

## Execution Context

Tests operate within `test_shim_context.py` context:
- Isolated execution environment
- Coverage/type data collection
- State reset between tests
- Resource cleanup

See individual test files for specific transformation verification.
