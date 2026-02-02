<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Instrumentation Fixtures

**Parent:** `../AGENTS.md`

Test fixtures for bytecode instrumentation and coverage tracking.

## Overview
Python modules used to test the instrumentation pipeline that enables runtime code tracing and coverage collection. These fixtures test both basic instrumentation mechanics and complex scenarios involving inheritance, comparisons, and proxy builtins.

## Files

### comparison.py
Tests instrumentation of comparison operations.

### covered_branches.py
Tests branch coverage tracking during instrumentation.

### covered_classes.py
Tests class-level coverage tracking.

### covered_functions.py
Tests function-level coverage tracking.

### covered_lines.py
Tests line-level coverage tracking.

### inherited.py
Tests instrumentation of inherited methods and attributes.

### mixed.py
Tests mixed instrumentation scenarios combining multiple features.

### proxy_builtins.py
Tests instrumentation interaction with Python builtins (list, dict, str, etc.) through proxy mechanisms.

### simple.py
Basic instrumentation fixture for simple test cases.

## Parent Documentation
See ../AGENTS.md for fixture category overview.

---
Timestamp: 2026-01-30
