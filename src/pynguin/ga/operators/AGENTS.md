<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Genetic Algorithm Operators

**Parent**: `../AGENTS.md`
**Module**: `pynguin.ga.operators`
**Timestamp**: 2026-01-30

## Overview

This module provides core operators for genetic algorithms used in Pynguin's test case generation. It implements selection, crossover, mutation, and ranking strategies essential for evolutionary test generation.

## Core Components

### Selection Functions (`selection.py`)

**Purpose**: Choose individuals from population for reproduction based on fitness.

#### `Selectable` (ABC)
- Abstract base for objects that can be selected
- Requires `get_fitness()` and `get_fitness_for(fitness_function)` implementations
- Used to ensure selection functions work with fitness-aware chromosomes

#### `SelectionFunction[T]` (Generic ABC)
- Base class for all selection strategies
- **Properties**:
  - `maximize`: Boolean flag for fitness maximization vs. minimization
  - Controls direction of selection pressure

**Selection Strategies**:

1. **RandomSelection**
   - Uniformly random choice from population
   - No fitness consideration (null selector for control)
   - No maximize property

2. **RankSelection**
   - Ranked-based exponential selection
   - Uses bias parameter from configuration (`rank_bias`)
   - Formula: `bias^(-i)` weighted selection favoring top-ranked individuals
   - Configurable bias: default from `config.search_algorithm.rank_bias`
   - Requires sorted population (best first)

3. **TournamentSelection**
   - Stochastic tournament with configurable size
   - Tournament size from `config.search_algorithm.tournament_size`
   - Selects individual with best fitness in random tournament sample
   - Respects `maximize` flag for direction
   - Higher tournament sizes → stronger selection pressure

### Crossover Functions (`crossover.py`)

**Purpose**: Combine genetic material from two parents.

#### `CrossOverFunction[T]` (Generic ABC)
- Abstract base for crossover strategies
- Single method: `cross_over(parent_1, parent_2)` - mutates parents in place

**Implementations**:

1. **SinglePointRelativeCrossOver**
   - Relative splitting point (not absolute position)
   - Split point: random value [0, 1] applied to each parent's size independently
   - Example: 70% split on 10-element parent = position 7, on 20-element parent = position 14
   - Offspring size: `<= max(parent1_size, parent2_size)`
   - Modifies both parents directly
   - Guards: skips if either parent has size < 2

### Ranking Functions (`ranking.py`)

**Purpose**: Assign dominance ranks to population for multi-objective optimization.

#### `RankedFronts[C]` (Dataclass)
- Container for ranked solutions grouped by Pareto front
- **Methods**:
  - `get_sub_front(rank)`: Returns solutions at given rank (0-indexed)
  - `get_number_of_sub_fronts()`: Total front count

#### `RankingFunction[C]` (ABC)
- Base for ranking algorithms
- Single abstract method: `compute_ranking_assignment(solutions, uncovered_goals) -> RankedFronts`
- Takes uncovered fitness goals into account

**Implementations**:

1. **RankBasedPreferenceSorting**
   - MOSA (Many-Objective Sorting Algorithm) ranking
   - Two-phase ranking:
     - Phase 1: Preference sorting for rank-0 front (best solution per goal)
     - Phase 2: Non-dominated sorting for remaining solutions
   - Uses `PreferenceSortingComparator` for phase 1
   - Uses `DominanceComparator` for phases 2+
   - Assigns explicit `rank` property to each chromosome
   - Stops when population size limit reached

2. **fast_epsilon_dominance_assignment**
   - Crowding distance variant (epsilon-dominance)
   - Based on Köppen & Yoshida, LNCS vol. 4403, 2007
   - Assigns `distance` property to each solution in front
   - Distance reflects sparsity: `(n_front - n_min_solutions) / n_front`
   - Used for tie-breaking in crowded regions

### Comparators (`comparator.py`)

**Purpose**: Compare chromosomes for dominance and preference.

- `DominanceComparator`: Multi-objective dominance (Pareto-based)
- `PreferenceSortingComparator`: Single-objective preference for specific goal

## Architecture Patterns

### Generics & Type Safety
- All major classes use `Generic[T]` with `TypeVar` bounds
- `T bound=Chromosome` ensures type safety across inheritance
- Enables reuse across different chromosome types (TestCase, TestSuite, etc.)

### Configuration Integration
- Selection bias: `config.search_algorithm.rank_bias`
- Tournament size: `config.search_algorithm.tournament_size`
- Population size: `config.search_algorithm.population`
- Design enables runtime strategy switching via configuration

### Mutation vs. Creation
- **Crossover**: Modifies parents in-place
- **Ranking**: Assigns properties (rank, distance) to existing chromosomes
- **Selection**: Returns reference to existing individuals (no copying)

## Data Flow

```
Population
    ↓ Selection (SelectionFunction)
    → Parent pair selected
    ↓ Crossover (CrossOverFunction)
    → New offspring from parents
    ↓ Ranking (RankingFunction)
    → Assign fitness ranks & distances
    ↓ Selection (next generation)
```

## Key Dependencies

- `pynguin.ga.chromosome`: Chromosome base class
- `pynguin.configuration`: Runtime settings
- `pynguin.utils.randomness`: Stochastic utilities
- `pynguin.utils.orderedset`: Ordered set for goal tracking

## Extension Points

- Implement new `SelectionFunction` for different selection pressure
- Implement new `CrossOverFunction` for different recombination strategies
- Implement new `RankingFunction` for different multi-objective orderings
- Extend comparators for domain-specific dominance definitions
