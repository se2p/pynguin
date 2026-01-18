#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""LLM-based test refinement for readability and assertion improvement."""

from __future__ import annotations

import ast
import logging
import sys
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pynguin.refinement.pipeline import TestRefiner
from pynguin.refinement.llm_client import LLMClient
from pynguin.refinement.readability_metrics import compute_all as compute_metrics

if TYPE_CHECKING:
    pass

_LOGGER = logging.getLogger(__name__)


def refine_generated_tests(
    test_file_path: Path, 
    module_name: str,
    llm_provider: str = "ollama",
    llm_base_url: str = "http://rhaegal.dimis.fim.uni-passau.de:15343",
    llm_model: str = "codellama:7b",
    llm_api_key: str | None = None,
    max_repair_iterations: int = 3,
    max_tests: int = 30,
) -> dict[str, any]:
    """Refine generated tests using LLM-based refinement pipeline.
    
    This is the main entry point called from generator.py after tests are exported.
    
    Args:
        test_file_path: Path to the generated test file
        module_name: Name of the module under test
        llm_provider: LLM provider to use ('ollama' or 'openai')
        llm_base_url: Base URL for Ollama LLM service (used when provider='ollama')
        llm_model: Model name to use (default: 'codellama:7b' for Ollama, 'gpt-4o-mini' for OpenAI)
        llm_api_key: API key for OpenAI (required when provider='openai')
        max_repair_iterations: Maximum repair attempts per test
        max_tests: Maximum number of tests to refine
        
    Returns:
        Dict with refinement statistics (tests_processed, tests_refined, repair_iterations, etc.)
        
    Examples:
        # Using Ollama (free, local)
        refine_generated_tests(
            test_file_path=Path("test_module.py"),
            module_name="my_module",
            llm_provider="ollama",
            llm_model="codellama:7b"
        )
        
        # Using OpenAI (paid, cloud)
        refine_generated_tests(
            test_file_path=Path("test_module.py"),
            module_name="my_module",
            llm_provider="openai",
            llm_model="gpt-4o-mini",
            llm_api_key="sk-..."
        )
    """
    _LOGGER.info("Starting LLM-based test refinement for %s (provider: %s, model: %s)", 
                 module_name, llm_provider, llm_model)

    start_wall = time.perf_counter()
    
    try:
        # Read generated test file
        with open(test_file_path, "r", encoding="utf-8") as f:
            raw_test = f.read()
        
        # Parse test functions
        tree = ast.parse(raw_test)
        import_nodes = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        test_functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        
        if import_nodes:
            module_wrapper = ast.Module(body=import_nodes, type_ignores=[])
            import_block = ast.unparse(module_wrapper) + '\n'
        else:
            import_block = ""
        
        # Import the module under test dynamically
        try:
            test_target_module = __import__(module_name)
            _LOGGER.info("Successfully imported module: %s", module_name)
        except ImportError as e:
            _LOGGER.error("Failed to import module %s: %s", module_name, e)
            # Return empty stats if module can't be imported
            return {
                "tests_processed": 0,
                "tests_refined": 0,
                "repair_iterations": 0,
                "failed_tests": 0,
                "readability_original": 0.0,
                "readability_refined": 0.0,
                "readability_delta": 0.0,
                "llm_calls": 0,
                "llm_input_tokens": 0,
                "llm_output_tokens": 0,
                "wall_time_seconds": 0.0,
            }
        
        # Initialize refiner with provider selection
        refiner = TestRefiner(
            api_key=llm_api_key,
            module_under_test=test_target_module,
            project_root=None,
            llm_provider=llm_provider,
            llm_base_url=llm_base_url,
            llm_model=llm_model
        )

        # Ensure usage is per-refinement-run, not per-process.
        try:
            refiner.llm_client.reset_usage()
        except Exception:
            pass
        
        # Track statistics
        stats = {
            "tests_processed": 0,
            "tests_refined": 0,
            "repair_iterations": 0,
            "failed_tests": 0,
            "readability_original": 0.0,
            "readability_refined": 0.0,
        }
        
        refined_tests = []
        
        # Process each test function (up to max_tests)
        for idx, func in enumerate(test_functions[:max_tests], 1):
            _LOGGER.info("Processing test %d/%d: %s", idx, len(test_functions), func.name)
            
            try:
                # Extract original code
                original_code = import_block + ast.unparse(func)
                
                # Compute original readability
                original_metrics = compute_metrics(original_code)
                stats["readability_original"] += original_metrics.get("aggregate", 0.0)
                
                # Run end-to-end refinement with repair loop
                result = refiner.process_test_end_to_end(
                    original_code=original_code,
                    max_retries=max_repair_iterations
                )
                
                stats["tests_processed"] += 1
                
                if result["success"]:
                    refined_code = result["final_code"]
                    
                    # Compute refined readability
                    refined_metrics = compute_metrics(refined_code)
                    stats["readability_refined"] += refined_metrics.get("aggregate", 0.0)
                    
                    # Extract just the function (remove imports)
                    refined_tree = ast.parse(refined_code)
                    refined_func = [n for n in refined_tree.body if isinstance(n, ast.FunctionDef)][0]
                    refined_tests.append(refined_func)
                    
                    stats["tests_refined"] += 1
                    stats["repair_iterations"] += result["iterations"]
                    
                    _LOGGER.info("Successfully refined %s (iterations: %d)", func.name, result["iterations"])
                else:
                    # Keep original if refinement failed
                    refined_tests.append(func)
                    stats["failed_tests"] += 1
                    _LOGGER.warning("Failed to refine %s: %s", func.name, result.get("error", "Unknown"))
                    
            except Exception as e:
                _LOGGER.exception("Error refining test %s: %s", func.name, e)
                refined_tests.append(func)  # Keep original
                stats["failed_tests"] += 1
        
        # Calculate average readability scores
        if stats["tests_processed"] > 0:
            stats["readability_original"] /= stats["tests_processed"]
            stats["readability_refined"] /= max(stats["tests_refined"], 1)
            stats["readability_delta"] = stats["readability_refined"] - stats["readability_original"]
        
        # Save refined test file
        if stats["tests_refined"] > 0:
            # Create new AST module with refined tests
            refined_module = ast.Module(body=import_nodes + refined_tests, type_ignores=[])
            refined_code = ast.unparse(ast.fix_missing_locations(refined_module))
            
            # Save to file (overwrite original or save as _refined)
            refined_path = test_file_path.parent / f"{test_file_path.stem}_refined.py"
            with open(refined_path, "w", encoding="utf-8") as f:
                f.write("# Test cases automatically generated by Pynguin (https://www.pynguin.eu).\n")
                f.write("# Refined using LLM-based test refinement pipeline.\n")
                f.write(refined_code)
            
            _LOGGER.info("Saved refined tests to %s", refined_path)
        
        _LOGGER.info("Refinement complete: %s", stats)

        try:
            usage = refiner.llm_client.get_usage()
        except Exception:
            usage = {}

        stats["llm_calls"] = int(usage.get("calls", 0) or 0)
        stats["llm_input_tokens"] = int(usage.get("input_tokens", 0) or 0)
        stats["llm_output_tokens"] = int(usage.get("output_tokens", 0) or 0)
        stats["wall_time_seconds"] = float(time.perf_counter() - start_wall)
        return stats
        
    except Exception as e:
        _LOGGER.exception("Test refinement failed: %s", e)
        return {
            "tests_processed": 0,
            "tests_refined": 0,
            "repair_iterations": 0,
            "failed_tests": 0,
            "error": str(e),
            "llm_calls": 0,
            "llm_input_tokens": 0,
            "llm_output_tokens": 0,
            "wall_time_seconds": float(time.perf_counter() - start_wall),
        }
