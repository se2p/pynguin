<!--
SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors

SPDX-License-Identifier: CC-BY-4.0
-->

<!-- Parent: ../AGENTS.md -->

# Docker - Pynguin Container Configurations

**Purpose:** Containerized execution environment for Pynguin, enabling isolated and reproducible test generation in controlled Docker environments.

**Last Updated:** 2026-01-30

## Files

### Dockerfile
Multi-stage Docker image for building and executing Pynguin:
- **Build stage:** Compiles Pynguin from source using Python 3.10.16, Poetry 1.8.4
- **Execute stage:** Lightweight runtime image with minimal dependencies
- **Version:** 0.45.0.dev0
- **Base image:** python:3.10.16-slim-bullseye
- **Features:**
  - Multi-stage build for minimal final image size
  - Environment variables: `PYNGUIN_DANGER_AWARE`, `PYTHONHASHSEED=0` (reproducible runs)
  - Includes optional dependencies: openai, numpy, typing
  - Accepts all Pynguin CLI parameters via Docker `run` command

## Docker Usage Guidelines for AI Agents

### Building the Image
```bash
docker build -t pynguin:latest .
```

### Running Pynguin in Container
The container accepts all Pynguin command-line arguments as Docker parameters:
```bash
docker run --rm pynguin:latest [pynguin-arguments]
```

### Key Environment Variables
| Variable | Value | Purpose |
|----------|-------|---------|
| `PYNGUIN_DANGER_AWARE` | Empty | Required acknowledgment that Pynguin executes third-party code |
| `PYTHONHASHSEED` | 0 | Ensures reproducible hash-based randomization |
| `PYTHONDONTWRITEBYTECODE` | 1 | Disables .pyc generation for faster execution |
| `PYTHONUNBUFFERED` | 1 | Real-time output stream monitoring |
| `PYNGUIN_VERSION` | 0.45.0.dev0 | Container's Pynguin version |

### Security Considerations
- The container acknowledges that Pynguin executes arbitrary code (third-party SUT)
- Use Docker isolation to contain potential side effects
- Mount volumes carefully; avoid exposing sensitive system paths
- Consider resource limits (`--cpus`, `--memory`) when running untrusted SUTs

### Multi-Stage Build Details
1. **Build Stage:** Copies project source, installs Poetry, runs `poetry build`
2. **Execute Stage:** Copies only the compiled wheel and entrypoint script
3. **Result:** Minimal image size; no build tools in runtime image

### Entrypoint
The container uses `pynguin-docker.sh` as the entrypoint script, which invokes the Pynguin CLI with passed arguments.

## Related Files
- `pynguin-docker.sh` - Entrypoint script (copied during build, not in source)
- `../poetry.lock` - Dependency lock file used during build
- `../pyproject.toml` - Poetry configuration

## Notes for Developers
- Agents should ensure `PYNGUIN_DANGER_AWARE` is set when spawning containers programmatically
- Set `PYTHONHASHSEED=0` is critical for deterministic test generation across container runs
- The slim base image keeps the final image lightweight (~800MB)
- Additional system dependencies (git, python-tk) are installed at runtime for compatibility
