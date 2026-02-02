<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Instrumentation Version Module

<!-- Parent: ../AGENTS.md -->

**Purpose**: Manages version tracking and compatibility for instrumented code to prevent re-instrumentation across multiple execution contexts.

## Overview

This module provides version tagging and detection mechanisms to identify instrumented modules and prevent redundant instrumentation. When Pynguin instruments code multiple times (e.g., during mutation testing or parallel execution), this module ensures each module is only instrumented once.

## Key Components

### Version Tagging

Instrumented modules receive version metadata embedded in their code:

- **Module Attributes**: Added to `__dict__` to mark instrumentation state
- **Version Markers**: Unique identifiers indicating instrumentation level and timestamp
- **Compatibility Tracking**: Version numbers indicate which instrumentation transformations were applied

### Instrumentation Detection

Mechanisms to detect if a module is already instrumented:

- **Attribute Checking**: Looks for version markers in module namespace
- **Code Analysis**: Scans for instrumentation markers in function/class definitions
- **Caching**: Maintains cache of instrumented module identifiers

### Version Compatibility

Ensures version compatibility when reloading or re-executing instrumented code:

- **Forward Compatibility**: Newer code can work with older instrumentation
- **Backward Compatibility**: Older code gracefully handles newer instrumentation
- **Mismatch Detection**: Identifies when version requirements don't match

## Integration Points

### Input Dependencies

- **Instrumentation Engine**: `pynguin.instrumentation.*`
- **Module Loading**: `pynguin.instrumentation.transformer.TransformingImporter`
- **Execution Environment**: `pynguin.testcase.execution.*`

### Output Dependencies

- **Mutation Analysis**: Mutations applied to already-instrumented modules
- **Test Execution**: Tests execute against instrumented code with version info
- **Statistics**: Version metrics tracked for instrumentation efficiency

## Key Design Patterns

- **Singleton Pattern**: Version registry maintains single source of truth
- **Caching Pattern**: Instrumented module versions cached to avoid re-detection
- **Tagging Pattern**: Metadata tags identify instrumentation level

## Configuration Options

- Instrumentation version scheme (semantic versioning, timestamps, hashes)
- Re-instrumentation policy (skip, warn, error)
- Version cache retention

## Related Documentation

- Parent: [../AGENTS.md](../AGENTS.md) - Instrumentation subsystem
- Sibling: [../AGENTS.md](../AGENTS.md) - Other instrumentation modules

---

*Generated: 2026-01-30*
*Module: pynguin.instrumentation.version*
