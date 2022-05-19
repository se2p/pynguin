#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides runtime variables for output."""
import enum


# pylint: disable=invalid-name
@enum.unique
class RuntimeVariable(str, enum.Enum):
    """Defines all runtime variables we want to store in the result CSV files.

    A runtime variable is either an output of the generation (e.g., obtained coverage)
    or something that can only be determined once the CUT is analysed (e.g., number of
    branches).

    It is perfectly fine to add new runtime variables in this enum, in any position, but
    it is essential to provide a unique name and a description for each new variable,
    because this description will become the text in the result.
    """

    # The module name for which we currently generate tests
    TargetModule = "TargetModule"

    # An identifier for this configuration for benchmarking
    ConfigurationId = "ConfigurationId"

    # An identifier for the project's name for benchmarking
    ProjectName = "ProjectName"

    # Total time spent by Pynguin to generate tests
    TotalTime = "TotalTime"

    # Number of iterations of the test-generation algorithm
    AlgorithmIterations = "AlgorithmIterations"

    # Execution results
    ExecutionResults = "ExecutionResults"

    # Obtained coverage of the chosen testing criterion(s)
    Coverage = "Coverage"

    # Obtained branch coverage
    BranchCoverage = "BranchCoverage"

    # Obtained line coverage
    LineCoverage = "LineCoverage"

    # The random seed used during the search.
    # A random one was used if none was specified in the beginning
    RandomSeed = "RandomSeed"

    # Obtained coverage (of the chosen testing criterion) at different points in time
    CoverageTimeline = "CoverageTimeline"

    # Obtained size values at different points in time
    SizeTimeline = "SizeTimeline"

    # Obtained length values at different points in time
    LengthTimeline = "LengthTimeline"

    # Obtained fitness values at different points in time
    FitnessTimeline = "FitnessTimeline"

    # Total number of exceptions
    TotalExceptionsTimeline = "TotalExceptionsTimeline"

    # Branch coverage over time
    BranchCoverageTimeline = "BranchCoverageTimeline"

    # Line coverage over time
    LineCoverageTimeline = "LineCoverageTimeline"

    # Total number of statements in the final test suite
    Length = "Length"

    # Number of tests in the resulting test suite
    Size = "Size"

    # Fitness value of the best individual
    Fitness = "Fitness"

    # Code Objects in the SUT
    CodeObjects = "CodeObjects"

    # Predicates in the bytecode of the SUT
    Predicates = "Predicates"

    # Lines in the bytecode of the SUT
    Lines = "Lines"

    # Accessible objects under test (e.g., methods and functions)
    AccessibleObjectsUnderTest = "AccessibleObjectsUnderTest"

    # Number of all generatable types, i.e., the types we can generate values for
    GeneratableTypes = "GeneratableTypes"

    # Branch Coverage that is achieved by simply importing the SUT
    ImportBranchCoverage = "ImportBranchCoverage"

    # Line Coverage that is achieved by simply importing the SUT
    ImportLineCoverage = "ImportLineCoverage"

    # The number of goals, i.e., number of fitness functions
    Goals = "Goals"

    # The number of test cases pynguin is able to collect from an initial population if
    # initial population seeding is enabled
    CollectedTestCases = "CollectedTestCases"

    # The number of found test cases independent of it can be collected or not
    FoundTestCases = "FoundTestCases"

    # Indicates if a suitable test module was found to seed initial testcases
    SuitableTestModule = "SuitableTestModule"

    def __repr__(self):
        return f"{self.name}"
