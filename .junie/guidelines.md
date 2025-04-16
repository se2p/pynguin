<!--
SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Pynguin Developer Guidelines

## Project Overview

Pynguin (PYthoN General UnIt test geNerator) is a tool for automated unit test generation for Python programs. It
requires Python 3.10.

## Project Structure

- `src/pynguin/`: Main package
    - `cli.py`: Command-line interface
    - `configuration.py`: Configuration settings
    - `generator.py`: Test generation logic
    - `assertion/`: Assertion generation
    - `ga/`: Genetic algorithm components
    - `instrumentation/`: Code instrumentation
    - `testcase/`: Test case generation
    - `utils/`: Utility functions
- `tests/`: Test cases
- `docs/`: Documentation

## Tech Stack

- **Python 3.10**: Required version
- **Poetry**: Dependency management
- **pytest**: Testing framework
- **Black**: Code formatting
- **isort**: Import sorting
- **mypy**: Type checking
- **ruff**: Linting
- **Sphinx**: Documentation

## Development Setup

1. Install Poetry: `make download-poetry`
2. Install dependencies: `make install`
3. Activate virtual environment: `poetry shell`

## Running Tests

- Run all tests: `make test`
- Run all checks: `pre-commit run --all-files`

## Executing Scripts

- Run Pynguin: `pynguin --project-path /path/to/project --output-path /path/to/output --module-name module.to.test`
- Format code: `make codestyle`
- Build documentation: `make documentation`
- Clean build artifacts: `make clean`

## Best Practices

1. **Code Style**:
    - Follow Black code style (88 characters per line)
    - Use Google Python Style Guide for docstrings
    - Keep functions and methods small and focused
    - Use pathlib instead of os.path or strings for file paths
    - Follow the existing project structure for new modules
    - Sort imports with isort

2. **Testing**:
    - Write tests for all new code
    - Run `make check` before submitting changes
    - Mirror the structure of the code under `tests/`

3. **Type Hints**:
    - Use type hints for all functions and methods
    - Use `from __future__ import annotations` for more concise type hints

4. **Contribution Workflow**:
    - If on main, create and checkout a new branch for your changes
    - Add changes
    - Add type hints and docstrings to new functions, methods, and classes
    - Add module docstrings to new modules
    - Add SPDX copyright headers to new files
    - Add tests for new changes
    - Run `pre-commit run --all-files` to format and check code
    - Run `pre-commit run --all-files` again, if ruff reformatted the code
    - Commit the changes

## LLM Agent Instructions

These rules are strictly enforced for automated code generation agents such as Junie:

LLM agents (Junie) **may**:

- Analyze existing code and documentation
- Suggest improvements or refactors
- Add new functions, methods, or classes within the existing structure
- Write unit tests for existing or new code
- Apply formatting, linting, and type checking
- Edit documentation in `docs/`
- Create new modules that follow the established structure and best practices

LLM agents (Junie) **must**:

- Use **Black** for formatting (88-char lines)
- Use **Google-style docstrings**
- Add **full type hints** (`from __future__ import annotations`)
- Add **SPDX headers** to new files:
    - `SPDX-FileCopyrightText: 2025 Pynguin Contributors`
    - Example: `SPDX-License-Identifier:` followed by `CC-BY-4.0`
- Modify only files in `src/`, `tests/`, or `docs/`
- Follow existing module and file structure
- Write or update **unit tests** for all changes
- Pass `pre-commit run --all-files`
- Keep diffs small and focused

LLM agents (Junie) **must not**:

- Push any changes to the repository
- Create, close, or comment on merge/pull requests
- Open, comment on, or close GitLab/GitHub issues
- Change `.git` or CI/CD configuration files
- Modify `poetry.lock` or `pyproject.toml` unless explicitly instructed
- Modify files outside the `src/`, `tests/`, or `docs/` directories
- Introduce dependencies without prior discussion in code comments
