<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Test Generation Algorithms (ga/algorithms)

<!-- Parent: ../AGENTS.md -->

The `algorithms/` directory contains implementations of multiple test generation strategies, from sophisticated evolutionary algorithms to simple random search. Each algorithm represents a different approach to exploring the test space.

## Overview

```
algorithms/
├── generationalgorithm.py          # Abstract base class for all algorithms
├── dynamosaalgorithm.py            # Dynamic Many-Objective Sorting Algorithm
├── abstractmosaalgorithm.py        # Base class for MOSA variants
├── mosaalgorithm.py                # Many-Objective Sorting Algorithm
├── llmosalgorithm.py               # LLM-guided MOSA variant
├── mioalgorithm.py                 # Many Independent Objective algorithm
├── wholesuitealgorithm.py          # Traditional whole-suite evolution
├── randomalgorithm.py              # Randoop-style feedback-directed random
├── randomsearchalgorithm.py        # Pure random search baseline
├── archive.py                      # Archive data structures (Coverage + MIO)
└── __init__.py                     # Module exports
```

## Base Class: GenerationAlgorithm

**File**: `generationalgorithm.py`

Abstract base for all test generation algorithms.

### Core Responsibilities

- **Lifecycle management**: `before_search_start()`, `after_search_iteration()`, `after_search_finish()`
- **Stopping conditions**: Monitors time, iterations, executions, coverage plateaus
- **Progress tracking**: Via `StoppingCondition` observers
- **Executor setup**: Manages `TestCaseExecutor` and `ComputationCache`

### Key Methods

```python
class GenerationAlgorithm(ABC, Generic[ArchiveT]):
    @abstractmethod
    def generate_tests(self) -> tsc.TestSuiteChromosome:
        """Main entry point - returns final test suite"""
        pass

    def before_search_start(self) -> None:
        """Called once at algorithm start"""
        pass

    def after_search_iteration(self) -> None:
        """Called after each generation/iteration"""
        pass

    def after_search_finish(self) -> None:
        """Called when stopping condition met"""
        pass
```

### Configuration

**Dependencies**:
- `executor`: `TestCaseExecutor` for running tests
- `test_cluster`: `TestCluster` with SUT class and dependencies
- `chromosome_factory`: `ChromosomeFactory` for creating individuals
- `stopping_conditions`: List of stopping conditions to check
- `observer`: Optional observer for search events

## DYNAMOSA Algorithm

**File**: `dynamosaalgorithm.py`

Dynamic Many-Objective Sorting Algorithm with adaptive goal management through structural dependencies.

### Key Innovation

**Control Dependency Graph**: Tracks which branch goals control which other goals
- Root branches (no dependencies) activated initially
- Child branches activated only when parent goal covered
- Avoids infeasible targets early in search

### Implementation Details

**Inner Classes**:

1. **`_BranchFitnessGraph`**: Control dependency graph
   - Nodes: Branch fitness functions
   - Edges: Control-dependency relationships
   - Methods: `get_root_goals()`, `get_child_goals(goal)`

2. **`_GoalsManager`**: Dynamic goal activation
   - Tracks active vs. inactive goals
   - Listens to archive updates
   - Activates goals when dependencies covered

### Algorithm Flow

```python
def generate_tests(self) -> tsc.TestSuiteChromosome:
    # 1. Build control dependency graph from branch goals
    goals_manager = _GoalsManager(graph)
    archive = CoverageArchive(goals_manager.active_goals)

    # 2. Initialize population (random chromosomes)
    population = self._create_initial_population()

    # 3. Main loop
    while not stopping_condition_met():
        # Evolve: Rank + select + crossover + mutate
        offspring = self._evolve_population(population)

        # Evaluate and archive
        for child in offspring:
            archive.update(child)

        # Activate new goals (dependency-driven)
        newly_covered = archive.covered_goals - goals_manager.active
        for goal in newly_covered:
            goals_manager.activate_children(goal)

        # Recompute ranking on expanded goal set
        population = self._rank_and_select(population + offspring)

    # 4. Return best solutions
    return archive.solutions
```

### Configuration Parameters

- `branch_comparison_function`: Dominance comparator for ranking
- `preference_sorting`: NSGA-II preference sorting implementation
- `selection_function`: Parent selection (usually tournament)
- `crossover_function`: Genetic crossover operator
- `alpha`: Mutation parameter (exponential decay)

### Advantages

- **Incremental goal discovery**: Focuses on achievable targets
- **Avoids infeasible goals**: Skips unreachable branches initially
- **Control-flow aware**: Respects program structure
- **Better convergence**: Less wasted effort on unreachable targets

## MOSA Algorithm (Base)

**File**: `abstractmosaalgorithm.py`

Abstract base for Many-Objective Sorting Algorithm variants.

### Core Concept

Multi-objective optimization where each coverage goal is a separate objective. Uses preference sorting to balance many goals simultaneously.

### Base Implementation

```python
class AbstractMOSAAlgorithm(GenerationAlgorithm):
    def generate_tests(self) -> tsc.TestSuiteChromosome:
        archive = CoverageArchive(goals)
        population = self._create_initial_population()

        while not stopping_condition_met():
            # Selection + Crossover + Mutation
            offspring = self._generate_offspring(population)

            # Evaluation
            for child in offspring:
                archive.update(child)

            # Preference sorting on uncovered goals
            ranking = self._preference_sort(population + offspring)
            population = ranking[:population_size]

        return archive.solutions
```

### Key Components

**Preference Sorting**:
- Rank all individuals by Pareto dominance on uncovered goals
- Within each rank, compute crowding distance
- Select individuals with best rank + crowding distance

**Uncovered Goals Filter**:
- Multi-objective fitness only considers uncovered goals
- Covered goals already in archive, no need to waste objectives

## MOSA Algorithm (Standard)

**File**: `mosaalgorithm.py`

Standard MOSA implementation - activates all coverage goals from the start.

### Configuration

- `branch_comparison_function`: Comparator for goal dominance
- `preference_sorting`: Preference sorting function
- `selection_function`: Parent selection
- `crossover_function`: Genetic crossover
- `alpha`: Mutation parameter

### When to Use

- Simpler codebase with few branches
- All goals potentially reachable
- Want straightforward many-objective optimization

## LLM-Guided MOSA

**File**: `llmosalgorithm.py`

MOSA variant with LLM guidance for test generation.

**Note**: Experimental feature. See implementation for LLM integration details.

## MIO Algorithm

**File**: `mioalgorithm.py`

Many Independent Objective algorithm with adaptive parameter tuning.

### Key Innovation

**Adaptive Parameters**: Adjusts search behavior as coverage increases
- `Pr`: Probability random vs. archive-sampled (explores → exploits)
- `n`: Population size per target (large → small)
- `m`: Mutations per sample (few → many)

### Algorithm Flow

```python
def generate_tests(self) -> tsc.TestSuiteChromosome:
    archive = MIOArchive(goals)
    progress = 0.0

    while not stopping_condition_met():
        # Adaptive parameters based on coverage progress
        progress = compute_coverage_percentage()
        Pr = interpolate(0.5, 0.0, progress / 0.85)
        n = interpolate(5, 1, progress / 0.85)
        m = interpolate(1, 10, progress / 0.85)

        for target in archive.targets:
            # Generate new solution
            if random() < Pr:
                test = self._create_random_test_case()  # Exploration
            else:
                test = archive.sample(target).clone()   # Exploitation

            # Mutate m times
            for _ in range(m):
                mutate(test)
                archive.update(test, target)

        # Shrink populations during focused phase
        if progress >= 0.85:
            archive.shrink_populations()

    return archive.solutions
```

### Archive Specialization (MIOArchive)

**Different from CoverageArchive**:
- Stores **population per target**, not just best test
- Tracks **h-value** (1.0 - normalized_fitness) for each test
- **Sampling strategy**: Favors targets with low sampling counter
- **Shrinking**: Reduces population size during focused phase

### Configuration

- `population_size`: Initial population per target
- `alpha`: Mutation decay parameter
- `selection_function`: Parent selection

### When to Use

- Large search spaces with many independent goals
- Adaptive behavior needed (exploration → exploitation)
- Resource-constrained settings (time/budget)

## Whole Suite Algorithm

**File**: `wholesuitealgorithm.py`

Traditional evolutionary algorithm operating on complete test suites as single individuals.

### Concept

Evolves **entire suites** as monolithic chromosomes, not individual test cases. Each individual = complete test suite.

### Algorithm Flow

```python
def generate_tests(self) -> tsc.TestSuiteChromosome:
    archive = CoverageArchive(goals) if archive_enabled else None
    population = [create_random_suite() for _ in range(population_size)]

    while not stopping_condition_met():
        # Select parents
        parent1 = selection_function(population)
        parent2 = selection_function(population)

        # Produce offspring
        offspring = [parent1.clone(), parent2.clone()]
        if random() < crossover_probability:
            offspring = cross_over_function(offspring)

        for child in offspring:
            child.mutate(self.mutator)

        # Keep better pair
        for child in offspring:
            if is_better(child, parent):
                replace parent with child

        # Elitism: Preserve best
        population = preserve_best_k(population, elite_size)

        # Archive update (optional)
        if archive:
            for suite in population:
                archive.update(suite)

    # Return solutions
    if archive:
        return archive.solutions  # Best individual per goal
    else:
        return best_individual(population)  # Single best suite
```

### Key Features

**Elitism**:
- Preserves best individuals across generations
- Prevents loss of good solutions

**Suite-Level Mutation**:
- Mutates individual tests within suite
- Adds/removes test cases
- Keeps suite size manageable

**Fitness Aggregation**:
- Suite fitness = aggregate of test case fitness
- Multi-objective ranking across all goals

### Configuration

- `population_size`: Number of suite individuals
- `selection_function`: Parent selection method
- `crossover_function`: Suite-level crossover
- `crossover_probability`: Probability of crossover
- `elite_size`: Number of best to preserve
- `use_archive`: Enable archive for tracking goals

### When to Use

- Prefer traditional EA over many-objective approaches
- Want suite-level optimization (minimize total length)
- Compatibility with EvoSuite-like behavior

## Random Algorithm

**File**: `randomalgorithm.py`

Randoop-style feedback-directed random test generation without genetic operators.

### Algorithm Flow

```python
def generate_tests(self) -> tsc.TestSuiteChromosome:
    passing = TestSuiteChromosome()
    failing = TestSuiteChromosome()

    while not stopping_condition_met():
        # Pick random method from test cluster
        method = random.choice(test_cluster.get_methods())

        # Build test: Select random existing tests + random inputs
        test = TestCaseChromosome()
        for _ in range(random.randint(0, max_sequence_length)):
            # Either use existing test or create new random call
            if failing.size > 0 and random() < reuse_probability:
                test = random.choice(failing).clone()
            else:
                test.add_statement(random_method_call())

        # Execute
        result = executor.execute(test)

        # Classify and store
        if result.has_exceptions:
            failing.add_test_case(test)
        else:
            passing.add_test_case(test)

        # Remove duplicates
        remove_duplicates(passing, failing)

    return passing  # Return only passing tests
```

### Key Characteristics

**No Genetic Operators**:
- No crossover
- No mutation operators
- Pure random generation

**Feedback-Directed**:
- Uses existing tests as building blocks
- Reuses failing tests to guide generation
- Maintains passing vs. failing separation

**Simplicity**:
- Baseline for comparison
- Fast for quick coverage gains
- Can find simple test cases quickly

### When to Use

- Baseline/sanity check against evolutionary algorithms
- Very simple classes with few methods
- Quick coverage estimation
- Comparison studies

## Random Search Algorithm

**File**: `randomsearchalgorithm.py`

Pure random search baseline - generates random test suites without any guidance.

### Algorithm Flow

```python
def generate_tests(self) -> tsc.TestSuiteChromosome:
    best_suite = TestSuiteChromosome()

    while not stopping_condition_met():
        # Generate completely random test suite
        suite = create_random_test_suite(
            size=random.randint(1, max_suite_size)
        )

        # Evaluate
        evaluate(suite)

        # Keep if better
        if is_better(suite, best_suite):
            best_suite = suite

    return best_suite
```

### Characteristics

**Pure Randomness**:
- No memory of previous tests
- No guidance from coverage feedback
- Completely independent iterations

**Minimal Overhead**:
- Cheapest baseline
- Useful for understanding search difficulty
- Reference point for algorithm improvements

### When to Use

- Absolute minimum baseline
- Sanity checking (should beat random)
- Academic comparison studies

## Archive Framework

**File**: `archive.py`

Data structures for managing coverage and candidate solutions.

### CoverageArchive

Used by MOSA, DYNAMOSA, Whole Suite.

**Purpose**: Track shortest test case covering each goal.

**Key Methods**:
- `update(individual)`: Add solution, keep shortest per goal
- `add_goals(new_goals)`: Dynamically add new coverage goals
- `covered_goals`: Set of goals with solutions
- `uncovered_goals`: Goals still needing solutions
- `solutions`: Best test case per covered goal
- `on_target_covered`: Callback when goal covered

**Properties**:
- Automatically minimizes test length as secondary criterion
- Supports dynamic goal addition (DYNAMOSA)
- Tracks coverage percentage

### MIOArchive

Specialized for MIO algorithm.

**Purpose**: Maintain population per target with adaptive shrinking.

**Key Differences**:
- Stores **multiple tests per goal** (population)
- Tracks **h-value** (1.0 - normalized_fitness)
- **Sampling counter**: Favors underexplored targets
- **Shrinking**: Reduces population during focused phase

**Key Methods**:
- `update(individual, target)`: Add to target's population
- `sample(target)`: Select test to mutate (favors low counter)
- `shrink_populations()`: Reduce sizes for exploitation
- `is_covered(target)`: True if h=1.0 found

## Selection & Ranking

Used across algorithms for parent selection and population ranking.

### Selection Strategies

**RandomSelection** (`operators/selection.py`):
- Uniform random selection
- Used for baseline/comparison

**TournamentSelection**:
- Select best from random tournament (size=k)
- Configurable tournament size
- Common in evolutionary algorithms

**RankSelection**:
- Bias selection by fitness rank
- Better individuals chosen more often
- Prevents selection pressure dominance

### Ranking for Multi-Objective

**RankBasedPreferenceSorting** (`operators/ranking.py`):
- NSGA-II style Pareto ranking
- Rank 1 = non-dominated solutions
- Within rank: compute crowding distance
- Select by rank + crowding

**Fast Epsilon Dominance**:
- Efficient crowding distance computation
- Numerical stability via epsilon values
- Assigns distance metric to chromosome

## Genetic Operators

**File**: `operators/crossover.py`, `operators/comparator.py`

### Crossover

**SinglePointRelativeCrossover**:
- Choose random split point r ∈ [0, 1]
- Split parent1 at ⌊(size1-1) × r⌋ + 1
- Split parent2 at ⌊(size2-1) × r⌋ + 1
- Exchange suffixes, creating two offspring
- Works with variable-length chromosomes

### Comparators

**GoalCoverageComparator**:
- Multi-objective dominance checking
- Compares fitness values on uncovered goals
- Individual A dominates B if:
  - Better on at least one goal, AND
  - Not worse on any goal

## Configuration & Factory

**Factory file**: `generationalgorithmfactory.py` (in parent directory)

Routes to appropriate algorithm based on `config.Algorithm`:
- `DYNAMOSA` → `DynamosaAlgorithm`
- `MOSA` → `MOSAAlgorithm`
- `MIO` → `MIOAlgorithm`
- `WHOLE_SUITE` → `WholeSuiteAlgorithm`
- `RANDOM` → `RandomAlgorithm`
- `RANDOM_SEARCH` → `RandomSearchAlgorithm`

Creates appropriate:
- Archive (CoverageArchive or MIOArchive)
- Fitness functions
- Stopping conditions
- Selection/crossover/ranking operators

## Patterns & Best Practices

### Choosing an Algorithm

| Algorithm | Best For | Complexity | Coverage |
|-----------|----------|-----------|----------|
| **DYNAMOSA** | Control-flow complex code | HIGH | Excellent (finds all reachable) |
| **MOSA** | Standard cases | MEDIUM | Very Good (all goals active) |
| **MIO** | Large search spaces, adaptive | MEDIUM | Good (adaptive exploration) |
| **Whole Suite** | EvoSuite-like behavior | MEDIUM | Good (suite-level) |
| **Random** | Baselines, simple code | LOW | Poor (feedback-only) |
| **Random Search** | Absolute baseline | LOW | Very Poor |

### Adding a New Algorithm

1. Extend `GenerationAlgorithm`:
   ```python
   class MyAlgorithm(GenerationAlgorithm[archive.CoverageArchive]):
       def generate_tests(self) -> tsc.TestSuiteChromosome:
           self.before_search_start()
           # Implementation
           self.after_search_finish()
           return test_suite
   ```

2. Register in factory (parent directory `generationalgorithmfactory.py`)

3. Add enum value in `config.py`

### Performance Considerations

- **Lazy evaluation**: Fitness computed only when accessed
- **Archive pruning**: Keeps only shortest test per goal
- **Early termination**: Stopping conditions checked each iteration
- **Caching**: Computation results cached until chromosome mutated

## Related Modules

- **`../chromosome.py`**: Chromosome base class with caching
- **`../testcasechromosome.py`**: Single test case chromosome
- **`../testsuitechromosome.py`**: Test suite chromosome
- **`../computations.py`**: Fitness/coverage computation framework
- **`../coveragegoals.py`**: Coverage goal definitions
- **`operators/`**: Selection, crossover, ranking operators
- **`testcase/`**: Test case representation and mutation

## Testing & Debugging

Each algorithm has:
- `_logger = logging.getLogger(__name__)`
- Search observers for iteration tracking
- Stopping condition callbacks
- Archive coverage tracking

For debugging:
- Enable logging to see algorithm progress
- Check archive coverage percentage each iteration
- Verify stopping condition triggering

---

**Key Files to Explore**:
- `dynamosaalgorithm.py` - Most sophisticated (control dependency graph)
- `abstractmosaalgorithm.py` - Many-objective base approach
- `mioalgorithm.py` - Adaptive parameter tuning
- `archive.py` - Data structure designs for different algorithms
