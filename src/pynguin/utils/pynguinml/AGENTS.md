<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# ML Module - AGENTS.md

<!-- Parent: ../AGENTS.md -->

Machine Learning-specific testing infrastructure for handling ML-specific parameters, constraints, and resources.

**Location:** `/src/pynguin/utils/pynguinml/`

## Module Overview

Specialized utilities for testing machine learning code, including parameter handling, constraint validation, and framework-specific resource management.

## Key Components

### ML Parameter Module
**File:** `mlparameter.py`
**Purpose:** Representation of ML-specific parameters

**Key Features:**
- Parses parameter constraints (shape, dtype, value ranges)
- Validates constraints during initialization
- Supports NumPy dtype mapping
- Common dtypes: int32, int64, float32, float64, complex64, complex128, bool, str

### ML Parsing Utilities
**File:** `ml_parsing_utils.py`
**Purpose:** Parse ML framework specifications and parameter definitions

### ML Test Factory Utilities
**File:** `ml_testfactory_utils.py`
**Purpose:** Factory methods for ML test generation

### ML Testing Resources
**File:** `ml_testing_resources.py`
**Purpose:** Resources and fixtures for ML test cases

### NumPy RNG
**File:** `np_rng.py`
**Purpose:** NumPy random number generator integration

## Integration Points

### With Test Generation
- `MLParameter` - Parameter constraints for ML models
- `ml_testing_resources` - ML test fixtures
- `np_rng` - NumPy array generation

### With ML Frameworks
- Framework-specific parameter parsing
- Dtype conversion and mapping
- Shape and constraint validation

## Common Usage Patterns

```python
# ML parameter handling
from pynguin.utils.pynguinml.mlparameter import MLParameter

# ML test generation
from pynguin.utils.pynguinml import ml_testfactory_utils

# NumPy array generation
from pynguin.utils.pynguinml.np_rng import <functions>
```

## Key Design Patterns

1. **Constraint Validation** - Validate ML parameter constraints early
2. **Factory Pattern** - ML test case creation
3. **Framework Abstraction** - Support multiple ML frameworks
4. **Dtype Mapping** - Framework-agnostic dtype handling

## Testing Considerations

- ML parameter validation catches invalid configurations early
- NumPy RNG deterministic seeding for reproducible arrays
- Constraint validation prevents runtime errors
- Shape validation ensures array compatibility

---

*Documentation timestamp: 2026-01-30*

*Parent directory: `/src/pynguin/utils/`*
