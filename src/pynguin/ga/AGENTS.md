<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Genetic Algorithm (GA) Module

<!-- Parent: ../AGENTS.md -->

The `ga/` directory contains Pynguin's core search-based test generation engine using genetic algorithms. This is the heart of Pynguin's evolutionary approach to automated test generation.

## Overview

This module implements multiple evolutionary algorithms for test generation:
- **DYNAMOSA**: Dynamic Many-Objective Sorting Algorithm with adaptive goal management
- **MOSA**: Many-Objective Sorting Algorithm for multi-objective optimization
- **MIO**: Many Independent Objective algorithm with adaptive parameters
- **Whole Suite**: Traditional whole-suite approach similar to EvoSuite
- **Random**: Randoop-style random test generation

## Directory Structure

```
ga/
├── algorithms/          # Algorithm implementations (DYNAMOSA, MIO, MOSA, etc.)
├── operators/           # Genetic operators (crossover, selection, ranking)
├── chromosome.py        # Abstract chromosome base class
├── computations.py      # Fitness and coverage computations
├── coveragegoals.py     # Coverage goal definitions (branch, line, checked)
├── generationalgorithmfactory.py  # Factory for algorithm instantiation
├── testcasechromosome.py    # Single test case chromosome
├── testsuitechromosome.py   # Test suite chromosome
└── postprocess.py       # Post-processing operations
```

## Core Components

### 1. Chromosome Hierarchy

**Base Class: `Chromosome` (chromosome.py)**
- Abstract base for all chromosomes (test cases and suites)
- Provides fitness/coverage computation caching via `ComputationCache`
- Defines core operations: `mutate()`, `cross_over()`, `clone()`
- Tracks fitness values, coverage, dominance rank, and crowding distance

**TestCaseChromosome** (testcasechromosome.py)
- Encodes a single test case as a chromosome
- Operations:
  - **Mutation**: Delete, change, or insert statements
  - **Crossover**: Single-point relative crossover
  - **Size control**: Automatic chopping when exceeding max length
- Tracks execution results and mutation count
- Mutation probabilities: test_delete, test_change, test_insert

**TestSuiteChromosome** (testsuitechromosome.py)
- Encodes a collection of test cases
- Suite-level operations:
  - Mutate individual test cases with probability 1/suite_size
  - Add new test cases with exponentially decreasing probability
  - Remove empty test cases
- Aggregates fitness across all test cases

### 2. Fitness & Coverage Framework

**computations.py** - Comprehensive fitness evaluation system:

**Fitness Functions**:
- `BranchDistanceTestCaseFitnessFunction`: Branch coverage for single test cases
- `BranchDistanceTestSuiteFitnessFunction`: Branch coverage for test suites
- `LineTestSuiteFitnessFunction`: Line coverage metric
- `StatementCheckedTestSuiteFitnessFunction`: Checked coverage via dynamic slicing

**Coverage Functions**:
- `TestSuiteBranchCoverageFunction`: Branch coverage percentage
- `TestSuiteLineCoverageFunction`: Line coverage percentage
- `TestSuiteStatementCheckedCoverageFunction`: Checked coverage percentage
- `TestSuiteAssertionCheckedCoverageFunction`: Assertion-based checked coverage

**Computation Cache** (`ComputationCache`):
- Lazy evaluation: Computes fitness/coverage only when needed
- Invalidation: Marks cache dirty when chromosome changes
- Multi-objective: Manages multiple fitness functions per chromosome
- Optimization: Infers coverage from fitness=0.0 for minimization

**Key Computation Functions**:
- `compute_branch_distance_fitness()`: Branch distance + code object coverage
- `compute_line_coverage()`: Line coverage from execution traces
- `compute_assertion_checked_coverage()`: Dynamic slicing for assertions
- `normalise()`: Normalize distance values to [0,1]

### 3. Coverage Goals

**coveragegoals.py** - Defines coverage targets:

**Goal Types**:
- `LineCoverageGoal`: Cover a specific line
- `CheckedCoverageGoal`: Check-cover a line via backward slicing
- `BranchlessCodeObjectGoal`: Enter a function/method without branches
- `BranchGoal`: Execute true/false branch of a predicate

**BranchGoalPool**:
- Creates all branch coverage goals from subject properties
- Manages branchless code objects and predicate branches
- Used by MOSA/DYNAMOSA algorithms

**Fitness Function Wrappers**:
- `BranchCoverageTestFitness`: Wraps branch goals with executor
- `LineCoverageTestFitness`: Wraps line goals
- `StatementCheckedCoverageTestFitness`: Wraps checked coverage goals

### 4. Algorithms (algorithms/)

**Base: `GenerationAlgorithm` (generationalgorithm.py)**
- Abstract base for all search algorithms
- Manages: executor, test cluster, chromosome factory, stopping conditions
- Lifecycle hooks: `before_search_start()`, `after_search_iteration()`, `after_search_finish()`
- Progress tracking via stopping conditions
- Observer pattern for search events

**DYNAMOSA** (dynamosaalgorithm.py)
- **Key Feature**: Dynamic goal management with structural dependencies
- **_GoalsManager**: Activates new goals when parents are covered
- **_BranchFitnessGraph**: Control-dependency graph for branch goals
  - Nodes = fitness functions, Edges = control dependencies
  - Root branches have no dependencies
  - Child branches activated when parent covered
- **Algorithm**:
  1. Start with root branches only
  2. Evolve population using NSGA-II-style ranking
  3. Update archive, activate new goals when parents covered
  4. Optional local search for coverage improvement
- **Advantages**: Focuses search on achievable goals, avoids infeasible targets

**MOSA** (mosaalgorithm.py)
- **Key Feature**: Many-objective optimization with all goals active
- Simpler than DYNAMOSA: all goals from the start
- Uses preference sorting on uncovered goals
- Fast epsilon dominance for crowding distance

**MIO** (mioalgorithm.py)
- **Key Feature**: Adaptive parameter tuning based on search progress
- **Parameters** (adjusted during search):
  - `Pr`: Probability of creating random test vs. sampling archive
  - `n`: Population size per target
  - `m`: Number of mutations before re-sampling
- **Phases**:
  - **Initial phase**: Exploration with high randomness
  - **Focused phase**: Exploitation with low randomness, smaller populations
- **Algorithm**:
  1. Sample or mutate test case
  2. Execute and evaluate against all targets
  3. Store in archive with h-value (normalized fitness)
  4. Shrink populations as search progresses

**Whole Suite** (wholesuitealgorithm.py)
- **Key Feature**: Traditional evolutionary algorithm on entire test suites
- Evolves suites as single individuals
- Uses archive to track covered goals and restrict fitness
- Elitism: Preserves best individuals
- Parent selection via configured selection function
- Offspring better than parents if:
  - Lower fitness, OR
  - Same fitness but shorter length

**Random Algorithm** (randomalgorithm.py)
- **Key Feature**: Randoop-style feedback-directed random testing
- No genetic operators, purely random generation
- Maintains two suites:
  - `test_chromosome`: Passing tests
  - `failing_test_chromosome`: Tests with exceptions
- **Algorithm**:
  1. Pick random public method
  2. Select random existing tests as building blocks
  3. Generate random inputs
  4. Execute and classify (passing/failing)
  5. Discard duplicates and timeouts

### 5. Genetic Operators (operators/)

**Selection** (selection.py)
- `RandomSelection`: Uniform random selection
- `TournamentSelection`: Select best from random tournament
- `RankSelection`: Bias selection toward fitter individuals using rank

**Crossover** (crossover.py)
- `SinglePointRelativeCrossOver`:
  - Split point is relative (e.g., 70% of length)
  - Works with different-sized parents
  - Offspring size ≤ max(parent1.size, parent2.size)

**Ranking** (ranking.py)
- `RankBasedPreferenceSorting`: NSGA-II style preference sorting
- `fast_epsilon_dominance_assignment()`: Compute crowding distance
- Used for multi-objective optimization in MOSA/DYNAMOSA

**Comparators** (comparator.py)
- Dominance checking for multi-objective optimization
- Preference comparisons based on goal coverage

### 6. Archive Mechanisms (algorithms/archive.py)

**CoverageArchive**
- Used by MOSA, DYNAMOSA, Whole Suite
- Stores shortest test case covering each goal
- Tracks covered vs. uncovered goals
- Automatically optimizes test length as secondary criterion
- Can dynamically add new goals (DYNAMOSA)

**MIOArchive**
- Specialized for MIO algorithm
- Maintains population per target (not just best)
- Stores h-value (1.0 - normalized_fitness) with each solution
- **Selection strategy**: Favor targets with low sampling counter
- **Shrinking**: Reduces population size during focused phase
- **Coverage detection**: h=1.0 means target fully covered

**Archive Operations**:
- `update()`: Add new solutions, keep shortest for each goal
- `add_goals()`: Dynamically add goals (DYNAMOSA)
- `solutions`: Return best test cases covering goals
- Callbacks on target coverage for tracking

### 7. Factory (generationalgorithmfactory.py)

**TestSuiteGenerationAlgorithmFactory**
- Configures complete algorithm from configuration
- Creates:
  - Appropriate algorithm (DYNAMOSA, MIO, MOSA, etc.)
  - Fitness functions for configured metrics
  - Coverage functions
  - Archive (CoverageArchive or MIOArchive)
  - Selection, crossover, ranking functions
  - Stopping conditions
  - Test cluster (optionally filtered)
- **Seeding support**:
  - Initial population seeding from existing tests
  - Archive seeding from previous runs

**Stopping Conditions**:
- `MaxSearchTimeStoppingCondition`: Time budget
- `MaxIterationsStoppingCondition`: Iteration limit
- `MaxTestExecutionsStoppingCondition`: Execution budget
- `MaxCoverageStoppingCondition`: Coverage threshold
- `CoveragePlateauStoppingCondition`: No improvement plateau
- `MaxMemoryStoppingCondition`: Memory limit

## Patterns & Best Practices

### Adding a New Algorithm

1. **Extend `GenerationAlgorithm`**:
   ```python
   class MyAlgorithm(GenerationAlgorithm[arch.Archive]):
       def generate_tests(self) -> tsc.TestSuiteChromosome:
           self.before_search_start()
           # Algorithm logic
           self.after_search_finish()
           return test_suite
   ```

2. **Register in factory**:
   ```python
   _strategies = {
       config.Algorithm.MY_ALGO: MyAlgorithm,
   }
   ```

3. **Configure in config.py**: Add enum value

### Adding a New Fitness Function

1. **Extend appropriate base**:
   - `TestCaseFitnessFunction` for individual tests
   - `TestSuiteFitnessFunction` for suites

2. **Implement required methods**:
   ```python
   class MyFitness(ff.TestCaseFitnessFunction):
       def compute_fitness(self, individual) -> float:
           result = self._run_test_case_chromosome(individual)
           # Compute fitness from result
           return fitness_value

       def compute_is_covered(self, individual) -> bool:
           # Check if goal is covered
           return is_covered

       def is_maximisation_function(self) -> bool:
           return False  # Currently only minimization supported
   ```

3. **Register in factory**: Add to `_get_test_case_fitness_functions()`

### Adding a New Coverage Goal

1. **Extend `AbstractCoverageGoal`**:
   ```python
   class MyGoal(AbstractCoverageGoal):
       def is_covered(self, result: ExecutionResult) -> bool:
           # Check execution trace
           return covered
   ```

2. **Create fitness function wrapper**: Similar to `BranchCoverageTestFitness`

3. **Generate goals**: Add factory function like `create_branch_coverage_fitness_functions()`

### Mutation Strategies

**Test Case Mutation** (`TestCaseChromosome`):
- **Delete**: Remove random statements with probability 1/(size+1) each
- **Change**: Mutate statement internals OR replace with random call
- **Insert**: Add random statements with exponentially decreasing probability (α^exponent)
- **Chopping**: Automatically trim tests exceeding max length

**Test Suite Mutation** (`TestSuiteChromosome`):
- Mutate each test case with probability 1/suite_size
- Add new tests with probability α, α², α³, ... (exponential decay)
- Remove empty tests automatically

### Crossover Strategy

**Single-Point Relative**:
- Choose random split point r ∈ [0,1]
- Split parent1 at position ⌊(size1-1) × r⌋ + 1
- Split parent2 at position ⌊(size2-1) × r⌋ + 1
- Exchange suffixes between parents
- Works well with variable-length chromosomes

### Archive Usage Patterns

**For new goal covered**:
```python
def _on_target_covered(self, target: FitnessFunction):
    # Called automatically when archive detects new coverage
    # Use for: updating fitness functions, logging, etc.
```

**Dynamic goal addition** (DYNAMOSA):
```python
archive.add_goals(new_goals)
# Archive tracks both old and new goals
# Uncovered goals automatically updated
```

### Multi-Objective Optimization

**Preference Sorting** (MOSA/DYNAMOSA):
1. Compute Pareto fronts on uncovered goals only
2. Within each front, compute crowding distance
3. Select based on front rank + crowding distance

**Fast Epsilon Dominance**:
- More efficient than standard crowding distance
- Uses epsilon values for numerical stability
- Assigns distance value to chromosome for selection

## Key Algorithms Explained

### DYNAMOSA Control Flow

```
1. Initialize with root branches (no control dependencies)
2. Create random population
3. While resources_left() and uncovered_goals > 0:
   a. Evolve population (NSGA-II style)
   b. Update archive with offspring
   c. GoalsManager: If parent goal covered, activate children
   d. Recompute ranking on new goal set
   e. Optional: Local search on archive solutions
4. Return archive solutions
```

### MIO Adaptive Parameters

```
Initial Phase (progress < 85%):
  Pr: 0.5 → 0.0 (linear interpolation)
  n:  5 → 1    (linear interpolation)
  m:  1 → 10   (linear interpolation)

Focused Phase (progress ≥ 85%):
  Pr: 0.0 (always sample from archive)
  n:  1   (one test per target)
  m:  10  (many mutations per sample)
```

### Whole Suite Evolution

```
1. Initialize random population of test suites
2. While not stopping condition:
   a. Select two parents via selection function
   b. Clone parents to create offspring
   c. Crossover with probability p_crossover
   d. Mutate offspring
   e. Keep better pair (offspring vs. parents)
   f. Apply elitism (preserve best)
   g. Update archive if enabled
   h. Restrict fitness for covered goals
3. Return archive solutions OR best individual
```

## Coverage Metrics

### Branch Coverage
- **Goal**: Execute both true/false branches of each predicate
- **Fitness**: Branch distance + code object reachability
- **Best for**: Control flow exploration

### Line Coverage
- **Goal**: Execute each line in the module
- **Fitness**: Number of uncovered lines
- **Best for**: Simple coverage metric

### Checked Coverage
- **Goal**: Lines influenced by statement return values (via slicing)
- **Fitness**: Number of unchecked lines
- **Best for**: Ensuring assertions check meaningful code
- **Computation**: Dynamic slicing from each statement's return value

## Configuration Integration

**Algorithm selection**: `config.Algorithm` enum
**Metrics**: `config.CoverageMetric` (BRANCH, LINE, CHECKED)
**Search parameters**: `config.search_algorithm.*`
**Stopping conditions**: `config.stopping.*`

## Testing & Debugging

**Logging**: Each class has `_logger = logging.getLogger(__name__)`
**Statistics**: Runtime variables tracked via `pynguin.utils.statistics`
**Observers**: Search observers for iteration tracking, best individual logging

## Related Modules

- `testcase/` - Test case representation and mutation
- `analyses/` - Test cluster, module analysis
- `instrumentation/` - Code instrumentation for trace collection
- `slicer/` - Dynamic slicing for checked coverage
- `utils/` - Randomness, statistics, ordered sets

## Performance Considerations

- **Lazy fitness evaluation**: Computed only when needed, cached
- **Archive pruning**: Keeps only shortest test per goal
- **Execution batching**: Multiple test cases executed together
- **Incremental updates**: Only re-execute changed test cases

## References

- DYNAMOSA: Panichella et al., "Reformulating Branch Coverage as a Many-Objective Optimization Problem"
- MOSA: Panichella et al., "A Large Scale Empirical Comparison of State-of-the-Art Search-Based Test Case Generators"
- MIO: Andrea Arcuri, "Many Independent Objective (MIO) Algorithm for Test Suite Generation"
- EvoSuite: Gordon Fraser & Andrea Arcuri, "EvoSuite: Automatic Test Suite Generation for Object-Oriented Software"

---

**Key Files to Explore**:
- `algorithms/dynamosaalgorithm.py` - Most sophisticated algorithm with dependency graph
- `computations.py` - Complete fitness/coverage computation framework
- `chromosome.py` - Core chromosome abstraction with caching
- `generationalgorithmfactory.py` - See how everything fits together
