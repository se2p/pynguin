"""
TEST-LLM-REFINE: A tool for refining Pynguin-generated tests using Large Language Models.

This package provides functionality to capture state, interact with LLMs,
and validate test equivalence for automated test refinement.
"""

__version__ = "0.1.0"
__author__ = "Ahmed"

# Lazy imports to avoid dependency issues when only using specific modules
def __getattr__(name):
    if name == "TestRefiner":
        from .pipeline import TestRefiner
        return TestRefiner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")