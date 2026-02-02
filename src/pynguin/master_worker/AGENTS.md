<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

# Master-Worker Module

<!-- Parent: ../AGENTS.md -->

The `master_worker/` directory implements distributed test generation using a master-worker pattern for parallel execution across multiple processes or machines.

## Overview

This module enables:
- Distributed test generation coordination
- Master process managing overall search
- Worker processes executing tests in parallel
- Communication and result aggregation

## Directory Structure

```
master_worker/
├── client.py                  # Worker client implementation
├── master.py                  # Master coordinator
└── worker.py                  # Worker process logic
```

## Core Components

### 1. Master Coordinator (master.py)
- **Master**: Central coordinator for distributed search
- Manages multiple worker processes or remote nodes
- Distributes work to available workers
- Aggregates results and fitness evaluations
- Coordinates archive updates across workers
- Tracks global search progress

Master responsibilities:
- Work distribution strategy
- Load balancing
- Result collection and aggregation
- Archive synchronization
- Stopping condition monitoring

### 2. Worker Client (client.py)
- **WorkerClient**: Communication interface to remote workers
- Sends test generation tasks to workers
- Receives results and fitness evaluations
- Handles timeouts and failures
- Supports multiple transport mechanisms

Worker client functionality:
- Task encoding/transmission
- Result reception and decoding
- Health monitoring
- Retry logic for failures

### 3. Worker Process (worker.py)
- **Worker**: Individual worker process/node
- Executes assigned test generation tasks
- Evaluates fitness of test cases
- Reports results back to master
- May maintain local cache for efficiency

Worker responsibilities:
- Execute genetic operators (mutation, crossover)
- Evaluate fitness functions
- Run tests on local subject program
- Format and send results to master

## Architecture

### Communication Pattern
```
Master
  ├─ Worker1 (Process 1)
  ├─ Worker2 (Process 2)
  ├─ Worker3 (Remote Node)
  └─ WorkerN
```

### Work Distribution
1. Master creates initial population
2. Distributes individuals to workers
3. Workers evaluate fitness locally
4. Workers return results and new individuals
5. Master updates archive and breeds new population
6. Repeat until stopping condition

## Integration with GA

### Algorithm Extensions
- Multi-objective algorithms (MOSA, DYNAMOSA) support distributed evaluation
- Archive shared across workers (synchronized periodically)
- Search progress monitored at master level

### Fitness Evaluation
- Heavy computation (fitness evaluation) done by workers
- Master coordinates ordering
- Results aggregated for selection/ranking

## Performance Considerations

- **Parallelism**: Linear speedup with worker count (ideal case)
- **Communication overhead**: Minimized by batching tasks
- **Load balancing**: Workers report completion, master distributes new work
- **Synchronization**: Archive updates batched to reduce overhead
- **Local caching**: Workers may cache execution results

## Configuration

Master-worker mode typically enabled via:
- Configuration: `config.distributed=True`
- Worker count: `config.num_workers`
- Transport: TCP/Socket, MPI, or custom

## Related Modules

- `ga/` - Search algorithms adapted for distributed execution
- `testcase/` - Test cases transmitted between master and workers
- `configuration.py` - Distributed search parameters

## Key Files to Explore

- `master.py` - Master coordination logic and load balancing
- `worker.py` - Worker execution and result handling
- `client.py` - Communication protocol

---

**Timestamp**: 2026-01-30
