<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Genetic Algorithm Tests

**Parent:** `../AGENTS.md`

Comprehensive test suite for pynguin's genetic algorithm implementation, including chromosome management, fitness computation, operators, and stopping conditions.

## Directory Structure

### Core Algorithm Components

- **`test_chromosome.py`** - Basic chromosome representation
  - Chromosome creation and initialization
  - Chromosome state management
  - File size: ~1.6 KB

- **`test_chromosomefactory.py`** - Chromosome factory pattern
  - Factory-based chromosome creation
  - Default initialization strategies
  - File size: ~3.8 KB

- **`test_testcasechromosome.py`** - Test case as chromosome
  - Wrapping test cases as GA chromosomes
  - Mutation and crossover for test cases
  - File size: ~13.9 KB

- **`test_testsuitechromosome.py`** - Test suite as chromosome
  - Managing multiple test cases in GA population
  - Suite-level fitness evaluation
  - File size: ~7.8 KB

### Fitness & Computation

- **`test_computations.py`** - Fitness computations
  - Coverage goal evaluation
  - Fitness value calculation
  - File size: ~10.6 KB

- **`test_computations_cache.py`** - Computation caching
  - Cache for expensive fitness evaluations
  - Cache hit/miss tracking
  - File size: ~7.0 KB

- **`test_computations_fitness_utilities.py`** - Fitness utilities
  - Helper functions for fitness calculation
  - Normalization and aggregation
  - File size: ~10.8 KB

- **`test_coveragegoals.py`** - Coverage goal definitions
  - Line coverage goals
  - Branch coverage goals
  - Exception coverage goals
  - File size: ~15.7 KB

### Algorithm Execution

- **`test_generationalgorithmfactory.py`** - GA factory
  - Algorithm instantiation from config
  - Strategy selection (WHOLE_SUITE, SINGLE_TEST, etc.)
  - File size: ~3.5 KB

- **`test_generator.py`** - Test case generator
  - GA-driven test generation
  - Population evolution
  - File size: ~6.3 KB

- **`test_testcasefactory.py`** - Test case factory
  - Creating individual test cases
  - Mutation operators
  - File size: ~1.1 KB

### Specialized Features

- **`test_llmtestsuitechromosomefactory.py`** - LLM integration
  - LLM-based test suite generation
  - Blending LLM suggestions with GA
  - File size: ~6.3 KB

- **`test_postprocess.py`** - Post-processing (43.7 KB - LARGEST)
  - Test minimization
  - Assertion insertion
  - Test suite cleanup and optimization
  - File size: ~43.7 KB

### Subdirectories

- **`algorithms/`** - GA algorithm variants
  - 13 test modules for different GA strategies
  - Tests for: WHOLE_SUITE, SINGLE_TEST, DynaMOSA, MOSA, etc.

- **`operators/`** - Genetic operators
  - 9 test modules for mutation and crossover
  - Selection strategies
  - Operator probability and application

- **`stoppingconditions/`** - Termination criteria
  - 13 test modules for stopping condition evaluation
  - Time-based, coverage-based, iteration-based stopping

## Test Coverage

### By Component

| Component | Test Count | Purpose |
|-----------|-----------|---------|
| Chromosomes | 4 | Representation and mutation |
| Fitness | 3 | Computation and caching |
| Goals | 1 | Coverage goal definition |
| Algorithms | 13 | GA strategy variants |
| Operators | 9 | Mutation and crossover |
| Conditions | 13 | Algorithm stopping |
| Factories | 4 | Object creation patterns |
| Utilities | 1 | LLM integration |
| Postprocess | 1 | Result optimization |

### Statistics

- **Total Test Files:** 46 Python files
- **Total Size:** ~150+ KB
- **Subdirectories:** 3 (algorithms, operators, stoppingconditions)

## Key Testing Areas

1. **Chromosome Management**
   - Representation of test cases and suites as GA chromosomes
   - Fitness evaluation and caching
   - Mutation and crossover operators

2. **Algorithm Variants**
   - Whole suite generation
   - Single test generation
   - Multi-objective strategies (DynaMOSA, MOSA)

3. **Genetic Operators**
   - Probability-based application
   - Parameter tuning
   - Operator effectiveness

4. **Stopping Conditions**
   - Time-based termination
   - Coverage-based termination
   - Fitness stagnation detection

5. **Fitness Computation**
   - Coverage goal evaluation
   - Fitness function caching
   - Multi-objective fitness aggregation

## Integration Points

Tests verify GA integration with:
- `instrumentation/` - Coverage tracking during GA evolution
- `testcase/` - Test case representation and mutation
- `assertion/` - Assertion insertion in generated tests
- `fixtures/` - Example code for GA testing

## Usage Pattern

Tests follow pytest conventions:
- `test_*.py` files with test functions
- Fixtures for setup/teardown
- Parametrized tests for variant testing
- Mock objects for dependencies

See individual test files for specific behavior verification.
