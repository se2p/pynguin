<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Resources Module

<!-- Parent: ../AGENTS.md -->

The `resources/` directory contains template files and static resources used for test report generation and visualization.

## Overview

This module provides:
- HTML templates for test coverage reports
- Visualization templates
- Resource assets for report rendering

## Directory Structure

```
resources/
├── coverage-template.html     # HTML template for coverage reports
└── fans/                      # Report styling and assets
```

## Core Components

### 1. Coverage Report Template (coverage-template.html)
- Jinja2 template for HTML coverage reports
- Displays test coverage metrics visually
- Shows per-file, per-function, per-line coverage
- Includes interactive features for drill-down analysis

### 2. FANS Resources (fans/)
- Styling assets (CSS)
- JavaScript utilities for interactivity
- Image assets and icons
- Used by coverage template for rendering

## Template Variables

The coverage template typically receives:
- Coverage statistics (branch, line, checked coverage percentages)
- Per-module coverage details
- Per-function coverage breakdown
- Execution counts and trace information

## Integration Points

### With GA Module
- After test generation completes, coverage reports generated
- Uses final test suite and coverage metrics
- Renders results for user review

### With Test Report Generation
- Part of `--report` output from Pynguin CLI
- Generates HTML file for viewing results
- Embeds statistics from test suite execution

## Usage

Coverage reports are typically generated via:
```bash
pynguin --report <output_dir>
```

Report output includes:
- `report.html` - Main coverage report
- CSS/JS assets from `fans/`
- Coverage data embedded or linked

## Related Modules

- `generator.py` - Generates tests and statistics for reports
- `ga/` - Coverage metrics used in report generation
- CLI integration - Report output

## Key Files to Explore

- `coverage-template.html` - Report template structure and variables

---

**Timestamp**: 2026-01-30
