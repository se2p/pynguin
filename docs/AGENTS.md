<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# docs/

<!-- Parent: ../AGENTS.md -->

## Purpose

This directory contains the comprehensive Sphinx documentation for Pynguin. The documentation is organized into user guides, developer/contributor guides, and API reference documentation. The structure supports building HTML documentation with Sphinx using the Read the Docs theme.

## Key Files

| File | Purpose |
|------|---------|
| `conf.py` | Sphinx configuration file - defines extensions, theme (sphinx_rtd_theme), version info, intersphinx mappings |
| `index.rst` | Documentation root/home page - defines the main table of contents with three sections: User Guide, Contributor Guide, API Documentation |
| `api.rst` | API reference entry point - auto-generates module documentation using sphinx.ext.autodoc |
| `CODEOWNERS` | GitHub code ownership rules for documentation directory |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `user/` | User-facing documentation: installation, quickstart guide, usage examples, assertions, coverage, reproducibility |
| `dev/` | Developer/contributor documentation: contributing guidelines, architecture overview, development setup, extension points |
| `source/` | Static assets and example files used in documentation (images, example Python files, generated test files) |
| `_build/` | Generated documentation output directory (HTML, doctrees, images) - created by Sphinx build process, not version controlled |

## For AI Agents

### Building Documentation

To build the Sphinx documentation locally:

```bash
# From project root
cd docs/

# Install documentation dependencies
pip install sphinx sphinx-rtd-theme sphinx-autodoc-typehints hoverxref

# Build HTML documentation
sphinx-build -b html . _build/

# View in browser
open _build/index.html  # macOS
# or: xdg-open _build/index.html  # Linux
# or: start _build/index.html  # Windows
```

### Documentation Structure

- **User Guide**: Start with `user/intro.rst` for Pynguin overview, then `user/install.rst` and `user/quickstart.rst` for setup
- **Examples**: See `source/_static/example.py` (triangle) and `source/_static/queue_example.py` for test generation examples
- **Developer Guide**: Read `dev/overview.rst` for architecture details, genetic algorithms, and test generation process
- **API Reference**: Auto-generated from source code docstrings via `api.rst`

### Sphinx Extensions Used

- `sphinx.ext.autodoc` - Auto-generate API docs from docstrings
- `sphinx.ext.napoleon` - Support for NumPy/Google style docstrings
- `sphinx.ext.intersphinx` - Link to Python/pytest/Sphinx documentation
- `sphinx.ext.viewcode` - Add source code links
- `hoverxref.extension` - Tooltip hover references
- `sphinx_autodoc_typehints` - Type hint support in API docs

### Key Documentation Topics

1. **Test Generation Process**: See `dev/overview.rst` - covers genetic algorithms, module analysis, test cluster, test case construction/execution
2. **Safety Warning**: Pynguin executes code under test - requires `PYNGUIN_DANGER_AWARE` environment variable, recommend Docker isolation
3. **Algorithms**: Default is DYNAMOSA (Many-Objective Sorting Algorithm), configurable via CLI
4. **Assertion Generation**: Uses mutation analysis to generate regression assertions
5. **Master-Worker Architecture**: Fault-tolerant execution model for test generation

---

**Generated**: 2026-01-30
**Updated**: 2026-01-30
