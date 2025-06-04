#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides custom exception types."""


class ConfigurationException(BaseException):
    """An exception type that's raised if the generator has no proper configuration."""


class GenerationException(BaseException):
    """An exception during test generation.

    This type shall be used for all exceptions that occur during test generation and
    that are caused by the test-generation process.
    """


class ConstructionFailedException(BaseException):
    """An exception used when error occurs during construction of a test case."""


class TimerError(Exception):
    """A custom exception used to report errors in use of Timer class."""


class InstructionNotFoundException(BaseException):
    """A custom exception if no matching instruction is found for a search."""


class TestTimeoutException(BaseException):
    """Raised, if the execution took longer than the configured maximum duration."""


class SlicingTimeoutException(BaseException):
    """Raised, if slicing took longer than the configured maximum duration."""


class ConstraintValidationError(Exception):
    """Raised when a constraints for ML API contain faulty information."""


class ModuleNotImportedError(Exception):
    """Raised when trying to access a module that is not imported."""

    def __init__(self, name: str) -> None:
        """Create a new module not imported error.

        Args:
            name: The name of the module that was not imported
        """
        super().__init__(f"Module '{name}' is not imported.")
        self.name = name


class MinimizationFailureError(Exception):
    """Raised when minimizing a test case failed."""


class CoroutineFoundException(BaseException):
    """Raised when a coroutine is found in the SUT, which Pynguin cannot handle."""
