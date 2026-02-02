<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

<!-- Generated: 2026-01-30 | Updated: 2026-01-30 -->
<!-- Parent: ../AGENTS.md -->

# src/ - Pynguin Source Code Implementation

## Purpose

Contains the complete source code implementation of Pynguin, an automated unit test generation framework for Python. The main package `pynguin/` implements genetic algorithms (DYNAMOSA, MOSA, MIO), code instrumentation for coverage tracking, test case representation and execution, type inference, assertion generation, and optional LLM integration for test generation.

## Key Files

| File | Description |
|------|-------------|
| `pynguin/__init__.py` | Package entry point, exports main API (`run_pynguin`, `set_configuration`), configures pickle support for bytecode objects |
| `pynguin/__main__.py` | Main entry for `python -m pynguin` execution |
| `pynguin/__version__.py` | Version string definition |
| `pynguin/cli.py` | Command-line interface using simple_parsing, rich logging, and configuration handling |
| `pynguin/configuration.py` | Configuration dataclass with 100+ parameters for algorithms, coverage, search budget, output format, seeding, LLM, etc. |
| `pynguin/generator.py` | Core generator orchestration: setup, execution, statistics tracking, and post-processing |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `pynguin/analyses/` | Static analysis utilities (type inference, module parsing, seeding, constants extraction) |
| `pynguin/assertion/` | Assertion generation and mutation analysis for improving test oracle quality |
| `pynguin/ga/` | Genetic algorithm implementation (chromosomes, fitness functions, algorithms, operators) |
| `pynguin/instrumentation/` | Bytecode instrumentation for coverage tracking and dynamic analysis |
| `pynguin/testcase/` | Test case representation, execution engine, local search, statement types |
| `pynguin/utils/` | Utility modules (randomness, statistics, type tracing, AST utilities, logging) |
| `pynguin/slicer/` | Dynamic program slicing for test case minimization |
| `pynguin/large_language_model/` | LLM integration for test generation (prompts, parsing, caching) |
| `pynguin/master_worker/` | Distributed execution with master-worker architecture |
| `pynguin/resources/` | Embedded resources and configuration templates |
| `pynguin/pynguin-report/` | HTML report generation for test execution results |

## For AI Agents

### Working In This Directory

1. **Entry Points:**
   - CLI execution: `pynguin/cli.py` → `pynguin/generator.py` → algorithm selection
   - Programmatic API: `from pynguin import run_pynguin, Configuration`
   - Master-worker mode: `pynguin/master_worker/client.py`

2. **Core Workflow:**
   ```
   Configuration → Generator.generate() → Algorithm (DYNAMOSA/MOSA/MIO/LLM)
   → Test Factory → Statement Execution → Coverage Analysis → Assertion Generation
   → Export (PyTest format) → Statistics & Reports
   ```

3. **Module Dependencies:**
   - `configuration.py` defines all settings (read by all modules)
   - `analyses/module.py` parses target module and builds type system
   - `ga/generationalgorithmfactory.py` instantiates the selected algorithm
   - `testcase/execution.py` executes test cases in isolated environments
   - `instrumentation/tracer.py` tracks coverage during execution

4. **Active Development Areas:**
   - Performance optimization in core modules
   - Instrumentation improvements for better coverage tracking
   - Type system enhancements

### Testing Requirements

1. **Test Structure:**
   - Tests mirror source: `tests/pynguin/` matches `src/pynguin/`
   - Fixtures: `tests/fixtures/` with subdirectories for type_tracing, seeding, etc.
   - Integration tests: `tests/integration/` for end-to-end scenarios

2. **Key Test Commands:**
   - `pytest tests/pynguin/` - Run all unit tests
   - `pytest tests/integration/` - Run integration tests
   - `pytest -k instrumentation` - Run instrumentation-related tests
   - `make test` - Run full test suite with coverage

3. **Testing Patterns:**
   - Use `pytest-mock` for mocking complex dependencies
   - Use `tmp_path` fixture for file system isolation
   - Check `tests/fixtures/` for reusable test modules
   - Instrumentation tests often need actual Python modules to instrument

### Common Patterns

1. **Configuration Access:**
   ```python
   import pynguin.configuration as config

   # Read configuration (set by generator or tests)
   conf = config.configuration
   algorithm = conf.algorithm  # Algorithm.DYNAMOSA, etc.
   ```

2. **Module Analysis:**
   ```python
   from pynguin.analyses.module import generate_test_cluster

   # Parse module and build test cluster (callable objects)
   test_cluster = generate_test_cluster(module_name, module_path)
   ```

3. **Test Execution:**
   ```python
   from pynguin.testcase.execution import TestCaseExecutor

   # Execute test case and collect coverage
   executor = TestCaseExecutor(tracer)
   result = executor.execute(test_case)
   ```

4. **Instrumentation:**
   ```python
   from pynguin.instrumentation.machinery import install_import_hook

   # Install import hook to instrument modules on import
   with install_import_hook(module_name, tracer):
       # Imports here will be instrumented
       pass
   ```

5. **Type System:**
   ```python
   from pynguin.analyses.typesystem import Instance, ProperType

   # Type inference and checking throughout codebase
   inferred_type = type_system.to_type_info(value)
   ```

6. **Genetic Algorithm:**
   ```python
   from pynguin.ga.chromosome import Chromosome
   from pynguin.ga.computations import compute_fitness

   # Chromosome represents test suite or test case
   fitness = compute_fitness(chromosome, goals)
   ```

7. **Statement Construction:**
   ```python
   from pynguin.testcase.testfactory import TestFactory

   # Create statements (assignments, method calls, etc.)
   factory = TestFactory(test_cluster)
   statement = factory.create_statement(position, test_case)
   ```

8. **Logging:**
   ```python
   import logging

   _LOGGER = logging.getLogger(__name__)
   # Use _LOGGER throughout for consistent logging
   ```

9. **Statistics Tracking:**
   ```python
   from pynguin.utils.statistics.statistics import RuntimeVariable
   from pynguin.utils.statistics.statisticsbackend import get_statistics_backend

   # Track metrics during generation
   backend = get_statistics_backend()
   backend.set_output_variable(RuntimeVariable.Coverage, value)
   ```

10. **Error Handling:**
    ```python
    from pynguin.utils.exceptions import (
        GenerationException,
        ConfigurationException,
    )

    # Use custom exceptions for clarity
    raise ConfigurationException("Invalid configuration")
    ```

## Dependencies

### Internal Dependencies

- `configuration` is imported by nearly all modules
- `analyses/module` provides type information to `testcase/testfactory`
- `instrumentation/tracer` is used by `testcase/execution`
- `ga/` depends on `testcase/` for chromosome representation
- `assertion/` depends on `testcase/execution` for trace collection
- `utils/statistics` is used throughout for metrics tracking

### External Dependencies

**Core:**
- `bytecode` - Bytecode manipulation for instrumentation
- `simple_parsing` - CLI argument parsing
- `rich` - Terminal formatting and logging
- `jellyfish` - String similarity for seeding
- `networkx` - Graph analysis for control flow
- `ordered_set` - Ordered set data structure
- `astor` - AST to source code conversion (legacy)
- `isort`, `black` - Code formatting for generated tests

**Type System:**
- `typing_inspect` - Runtime type inspection
- `Deprecated` - Deprecation decorators

**LLM (Optional):**
- `openai` - OpenAI API client
- `tiktoken` - Token counting for LLM prompts

**Machine Learning (Optional):**
- `torch`, `transformers` - For ML-based features in `utils/pynguinml/`

**Development:**
- `pytest`, `pytest-cov`, `pytest-mock` - Testing framework
- `mypy` - Type checking
- `ruff` - Linting
- `sphinx` - Documentation generation

## Important Notes

1. **Safety:** Pynguin executes untrusted code. Always run in isolated environments (Docker recommended).

2. **Version-Specific Code:** `instrumentation/version/` contains Python version-specific handling (3.10, 3.11, 3.12, 3.13).

3. **Configuration is Global:** The `configuration.py` module uses a global singleton pattern. Tests must be careful to isolate configuration changes.

4. **Instrumentation Caching:** Instrumented bytecode is cached to avoid re-instrumentation overhead.

5. **Test Execution:** Tests execute in isolated environments with filesystem isolation (`utils/fs_isolation.py`) and import machinery control.

6. **LLM Integration:** Optional feature, requires API keys. Algorithm.LLM bypasses normal test generation and queries LLM directly.

7. **Master-Worker:** For parallel execution across multiple processes/machines. See `master_worker/` for client/server implementation.
