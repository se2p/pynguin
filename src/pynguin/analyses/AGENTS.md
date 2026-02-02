<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Analyses Module

<!-- Parent: ../AGENTS.md -->

The `analyses/` directory contains static analysis components for subject program understanding, including module analysis, type inference, and test cluster generation.

## Overview

This module performs comprehensive program analysis to:
- Build test clusters from subject program callables
- Perform type inference on generic types
- Analyze module structure and complexity
- Support seeding from existing tests

## Directory Structure

```
analyses/
├── constants.py             # Analysis constants and configuration
├── generator.py             # Test cluster generation from modules
├── module.py                # Module representation and access
├── modulecomplexity.py      # Module complexity metrics
├── seeding.py               # Seed test generation from existing tests
├── string_subtypes.py       # String type hierarchy analysis
├── syntaxtree.py            # Abstract syntax tree utilities
└── type_inference.py        # Generic type inference engine
├── typesystem.py            # Type system representation
```

## Core Components

### 1. Module Analysis (module.py)
- **ModuleAccessor**: Accesses Python modules and their callables
- Discovers classes, methods, functions within a module
- Tracks module dependencies and import structure
- Filters public vs. private members

### 2. Type System (typesystem.py)
- **GenericType**: Represents generic Python types (List[int], Dict[str, Any])
- **Type inference**: Resolves type parameters from annotations and usage
- Handles complex type hierarchies and bounds
- Supports Union, Optional, generic base classes

### 3. Type Inference (type_inference.py)
- Infers generic type parameters from class hierarchies
- Resolves type variables in method signatures
- Handles substitution of type bounds

### 4. Test Cluster Generation (generator.py)
- **TestCluster**: Collection of callable descriptions with dependency info
- Creates from subject module or custom callables
- Builds dependency graph for method/function calls
- Tracks class hierarchies for polymorphism

### 5. Seeding (seeding.py)
- Loads existing tests from files or test suites
- Extracts test cases for use as initial population
- Supports multiple test formats

### 6. Complexity Analysis (modulecomplexity.py)
- Computes module complexity metrics
- Analyzes cyclomatic complexity
- Used for search space characterization

## Key Patterns

### Module Access
```python
from pynguin.analyses.module import ModuleAccessor

accessor = ModuleAccessor(module)
callables = accessor.get_all_callables()
classes = accessor.get_classes()
```

### Type System
```python
from pynguin.analyses.typesystem import GenericType

# Parse complex types
list_int = GenericType.from_string("List[int]")
dict_type = GenericType.from_string("Dict[str, Any]")
```

### Test Cluster
```python
from pynguin.analyses.generator import TestClusterGenerator

generator = TestClusterGenerator()
cluster = generator.generate_cluster(module)
callables = cluster.get_all_callables()
```

## Related Modules

- `ga/` - Uses test clusters for search space definition
- `testcase/` - Test cases use analyzed type information
- `instrumentation/` - Complements dynamic analysis

## Key Files to Explore

- `typesystem.py` - Complete type system representation
- `generator.py` - Test cluster generation algorithm
- `module.py` - Module introspection utilities

---

**Timestamp**: 2026-01-30
