<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

<!-- Generated: 2026-01-30 | Updated: 2026-01-30 -->

# Pynguin - Automated Unit Test Generation for Python

## Purpose

Pynguin (IPA: ˈpɪŋɡuiːn) is a research tool for automated generation of unit tests for Python programs. It uses search-based techniques (genetic algorithms) to automatically generate test suites that achieve high code coverage. The tool is developed at the University of Passau and represents the first fully-automated unit test generator for general-purpose Python programs.

## Project Status

- **Python Support:** 3.10 (stable), 3.11-3.14 (experimental)
- **License:** MIT

## Key Files

| File | Description |
|------|-------------|
| `pyproject.toml` | Poetry project configuration, dependencies, and tool settings |
| `README.md` | Project overview, installation, and usage instructions |
| `Makefile` | Development commands (check, test, coverage, docs) |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `src/` | Main source code implementation (see `src/AGENTS.md`) |
| `tests/` | Comprehensive test suite with fixtures (see `tests/AGENTS.md`) |
| `docs/` | Sphinx documentation (user guides, API reference) (see `docs/AGENTS.md`) |
| `docker/` | Docker configurations for isolated execution (see `docker/AGENTS.md`) |
| `.run/` | PyCharm run configurations |
| `.idea/` | PyCharm IDE settings |
| `LICENSES/` | License texts (MIT, Apache-2.0, BSD-2-Clause, CC-BY-4.0, CC0-1.0) |

## For AI Agents

### Working In This Project

1. **Development Setup:**
   - Use Poetry for dependency management: `poetry install`
   - Python 3.10+ required
   - Run `make check` before committing (runs tests, linting, type checking)

2. **Code Quality Standards:**
   - **Linting:** Ruff (extensive ruleset enabled, see pyproject.toml)
   - **Type Checking:** mypy with strict settings
   - **Formatting:** Black formatter
   - **Documentation:** Google-style docstrings
   - **Testing:** pytest with >80% coverage requirement

### Testing Requirements

- **Unit Tests:** Located in `tests/` mirroring `src/` structure
- **Coverage:** Minimum 80%, configured in `tool.coverage` section
- **Test Framework:** pytest with plugins (pytest-cov, pytest-mock, pytest-sugar)
- **Run Tests:** `make test` or `pytest tests/`
- **Coverage Report:** `make cov` generates HTML report in `cov_html/`

### Common Patterns

1. **Module Structure:**
   - Source code in `src/pynguin/`
   - Tests in `tests/` with same directory structure
   - Fixtures in `tests/fixtures/` organized by feature area

2. **Genetic Algorithm Architecture:**
   - Algorithms in `src/pynguin/ga/algorithms/`
   - Operators (crossover, selection, mutation) in `src/pynguin/ga/operators/`
   - Test case representation in `src/pynguin/testcase/`

3. **Instrumentation:**
   - Code instrumentation in `src/pynguin/instrumentation/`
   - Version-specific handling in `src/pynguin/instrumentation/version/`
   - Instrumentation transformations for coverage tracking

4. **Type System:**
   - Type tracing and inference throughout codebase
   - Active optimization work to reduce execution overhead
   - Fixtures in `tests/fixtures/type_tracing/`

5. **LLM Integration (Optional):**
   - Large language model features in `src/pynguin/large_language_model/`
   - Requires `openai` extra: `poetry install --extras openai`
   - Assertion generation and test case prompting

## Dependencies

### Core Dependencies

- **astroid** - Python AST analysis
- **bytecode** - Python bytecode manipulation
- **networkx** - Graph algorithms (for control flow)
- **pytest** - Testing framework (used both for running Pynguin and generated tests)
- **black** - Code formatting
- **libcst** - Concrete syntax tree manipulation
- **Jinja2** - Template engine (for test generation)

### Optional Features ("--extras")

| Extra | Dependencies | Purpose |
|-------|--------------|---------|
| `openai` | openai, python-dotenv | LLM-based test generation |
| `numpy` | numpy | Numerical computation support |
| `typing` | mypy, typing-extensions | Enhanced type checking |
| `fandango-faker` | faker, fandango-fuzzer, xmltodict | Resource generation (test data) |

### Development Dependencies

- **mypy** - Static type checking
- **ruff** - Fast Python linter
- **pre-commit** - Git hooks for code quality
- **sphinx** - Documentation generation
- **coverage** - Code coverage measurement
- **hypothesis** - Property-based testing

## Architecture Overview

```
Pynguin Test Generation Pipeline:
1. Module Analysis → Parse Python code, build control flow graph
2. Algorithm Selection → Choose search strategy (DYNAMOSA, MIO, MOSA, etc.)
3. Test Generation → Genetic algorithm evolves test cases
4. Assertion Generation → Add assertions via mutation analysis or LLM
5. Output → Generated test suite as executable pytest tests
```

### Key Components

- **GA (Genetic Algorithms):** Core search-based test generation
- **Instrumentation:** Runtime code monitoring for coverage tracking
- **Assertion Generation:** Automated oracle creation
- **Test Case Representation:** Internal model for test cases
- **Slicer:** Program slicing for focused testing
- **Resources:** Test data generation (primitives, objects, collections)

## Common Tasks

| Task                     | Command/Location |
|--------------------------|------------------|
| Run all pre-commit hooks | `pre-commit run --all-files` |
| Run all checks | `make check` |
| Run tests | `make test` or `pytest` |
| Generate coverage | `make cov` |
| Build documentation | `make docs` |
| Format code | `black src/ tests/` |
| Run type checker | `mypy src/` |
| Run linter | `ruff check src/ tests/` |
| Generate tests for module | `pynguin --project-path /path --output-path /out --module-name foo.bar` |

## Navigation Tips

- **For algorithm work:** See `src/pynguin/ga/AGENTS.md`
- **For instrumentation:** See `src/pynguin/instrumentation/AGENTS.md`
- **For test case structure:** See `src/pynguin/testcase/AGENTS.md`
- **For LLM features:** See `src/pynguin/large_language_model/AGENTS.md`
- **For examples:** Browse `tests/fixtures/` subdirectories

## AI Agent Development Guidelines

### 1. Code Quality Standards

**SPDX Headers:**
All new source files must start with an SPDX license header:
```python
# This file is part of the Pynguin automated unit test generation framework.
# Copyright (C) 2024 Lukas Krodinger
# SPDX-License-Identifier: MIT
```

**Type Hints & Imports:**
- Use `from __future__ import annotations` at the top of all new modules
- All function parameters and return types must have type hints
- Enable strict mypy checking: `mypy src/`

**Documentation:**
- Use Google-style docstrings for all public functions and classes
- Include Args, Returns, and Raises sections where applicable
- Example:
```python
def generate_tests(module: str, timeout: int = 60) -> list[TestCase]:
    """Generate unit tests for the specified module.

    Args:
        module: Full module path (e.g., 'foo.bar.baz')
        timeout: Maximum generation time in seconds

    Returns:
        List of generated test cases

    Raises:
        ValueError: If module cannot be imported
    """
```

**Formatting:**
- Use Ruff for all formatting
- Maximum line length: 100 characters
- Run: `ruff check --fix src/` and `ruff format src/`

### 2. Testing Requirements

**Test Structure:**
- Unit tests located in `tests/` mirroring `src/` directory structure
- Example: Source at `src/pynguin/ga/foo.py` → Test at `tests/ga/test_foo.py`

**Testing Workflow:**
- Run before committing: `make test` or `pytest tests/`
- Use pytest fixtures from `tests/fixtures/` for common patterns
- Use parametrized tests for multiple input scenarios
- Test framework: pytest with plugins (pytest-cov, pytest-mock, pytest-sugar)

### 3. File Modification Boundaries

**Can Modify:**
- `src/` - Main source code
- `tests/` - Test suite
- `docs/` - Documentation
- `AGENTS.md` - This file (in manual section only)

**Cannot Modify (Without Explicit Authorization):**
- `pyproject.toml` - Poetry configuration and dependency management
- `poetry.lock` - Dependency lock file
- `.github/workflows/` - CI/CD configurations
- `.git/` - Git internals

**Dependency Changes:**
- Do NOT modify `pyproject.toml` for dependency changes without discussion
- Consult with project maintainers before adding new dependencies

### 4. Pre-commit Workflow

**Before Every Commit:**

1. Run pre-commit hooks:
   ```bash
   pre-commit run --all-files
   ```

2. May need to run twice if Ruff reformats files:
   ```bash
   pre-commit run --all-files
   pre-commit run --all-files  # Run again if first run made changes
   ```

3. Verify all checks pass before committing

4. Run full test suite:
   ```bash
   make test
   ```

### 5. Common Restrictions

**Version Control:**
- No pushing to remote repositories
- No force-pushing or rewriting history

**CI/CD & Dependencies:**
- Do not modify CI/CD configurations (`.github/workflows/`)
- Do not change dependency versions in `poetry.lock`
- Do not add new dependencies without discussion

**Development Practices:**
- Always work on feature branches (not `main`)
- Commit frequently with clear messages
- Create pull requests for review before merging to `main`

### 6. Quick Reference Checklist

Before marking work complete:

- [ ] Code follows SPDX header format (if new file)
- [ ] Type hints added with `from __future__ import annotations`
- [ ] Google-style docstrings for all public APIs
- [ ] Ruff formatting: `ruff check --fix && ruff format`
- [ ] Tests written/updated in `tests/` mirroring `src/`
- [ ] Pre-commit passes: `pre-commit run --all-files` (twice if needed)
- [ ] All tests pass: `make test`
- [ ] No modifications to protected files (pyproject.toml, poetry.lock, CI/CD)
