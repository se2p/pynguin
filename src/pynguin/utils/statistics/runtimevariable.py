#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides runtime variables for output."""

import enum


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

    # ========= Miscellaneous statistics =========

    # The module name for which we currently generate tests
    TargetModule = "TargetModule"

    # An identifier for this configuration for benchmarking
    ConfigurationId = "ConfigurationId"

    # An identifier of the cluster job
    RunId = "RunId"

    # An identifier for the project's name for benchmarking
    ProjectName = "ProjectName"

    # Total run time of Pynguin
    TotalTime = "TotalTime"

    # Time that Pynguin spent searching.
    SearchTime = "SearchTime"

    # Number of iterations of the test-generation algorithm
    AlgorithmIterations = "AlgorithmIterations"

    # The random seed used during the search.
    # A random one was used if none was specified in the beginning
    RandomSeed = "RandomSeed"

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

    # The cyclomatic complexity as defined by McCabe based on elements of the SUT,
    # whose AST is accessible via the test cluster.
    McCabeAST = "McCabeAST"

    # The cyclomatic complexity as defined by McCabe based on the CFG of the
    # Code Objects in the SUT.
    McCabeCodeObject = "McCabeCodeObject"

    # The number of lines in the source file
    LineNos = "LineNos"

    # The number of created mutants
    NumberOfCreatedMutants = "NumberOfCreatedMutants"

    # The number of killed mutants
    NumberOfKilledMutants = "NumberOfKilledMutants"

    # The number of mutants that caused a timeout
    NumberOfTimedOutMutants = "NumberOfTimedOutMutants"

    # The mutation score
    MutationScore = "MutationScore"

    # Store JSON serialized information about the signatures in the SUT, i.e.,
    # annotated and guessed parameter types as well as annotated and recorded
    # return types. Also store which types are base type matches of other types.
    SignatureInfos = "SignatureInfos"

    # Number of constructors
    NumberOfConstructors = "NumberOfConstructors"

    # ========= Values collected during search =========

    # Obtained coverage (of the chosen testing criterion(s)) at different points in time
    CoverageTimeline = "CoverageTimeline"

    # Obtained size values at different points in time
    SizeTimeline = "SizeTimeline"

    # Obtained length values at different points in time
    LengthTimeline = "LengthTimeline"

    # Obtained fitness values at different points in time
    FitnessTimeline = "FitnessTimeline"

    # Total number of exceptions
    TotalExceptionsTimeline = "TotalExceptionsTimeline"

    # ========= Values collected at the end of the search =========

    # Total number of statements in the resulting test suite
    Length = "Length"

    # Number of tests in the resulting test suite
    Size = "Size"

    # Fitness value of the best individual
    Fitness = "Fitness"

    # Obtained mean coverage of the chosen testing criterion(s)
    Coverage = "Coverage"

    # Obtained branch coverage
    BranchCoverage = "BranchCoverage"

    # Obtained line coverage
    LineCoverage = "LineCoverage"

    # Obtained checked coverage with no assertions
    StatementCheckedCoverage = "StatementCheckedCoverage"

    # ========= Values collected after post-processing and re-execution =========
    # These values might differ from the above values, if tests are flaky and thus
    # produce a different execution trace or the test have been modified
    # during post-processing.

    # Obtained checked coverage with assertions
    AssertionCheckedCoverage = "AssertionCheckedCoverage"

    # Total number of statements in the resulting test suite
    FinalLength = "FinalLength"

    # Number of tests in the resulting test suite
    FinalSize = "FinalSize"

    # Obtained branch coverage
    FinalBranchCoverage = "FinalBranchCoverage"

    # Obtained line coverage
    FinalLineCoverage = "FinalLineCoverage"

    # The number of assertions in the generated test suite
    Assertions = "Assertions"

    # The number of generated assertions that were removed, since
    # they do not increase the resulting checked coverage
    DeletedAssertions = "DeletedAssertions"

    # Which LLM strategy is applied. This is mainly
    # for final result grouping
    LLMStrategy = "LLMStrategy"

    # Number of total LLM calls
    TotalLLMCalls = "TotalLLMCalls"

    # Number of input tokens sent LLM to model
    TotalLLMInputTokens = "TotalLLMInputTokens"

    # Number of input tokens sent LLM to model
    TotalLLMOutputTokens = "TotalLLMOutputTokens"

    # Number of LLM responses with no python code within them
    TotalCodelessLLMResponses = "TotalCodelessLLMResponses"

    # Number of seconds LLM queries took
    LLMQueryTime = "LLMQueryTime"

    # Total of LLM test cases tha are merged into the population
    TotalLTCs = "TotalLTCs"

    # Number of parsed statements from LLM output
    LLMTotalParsedStatements = "LLMTotalParsedStatements"

    # Total number of statements from LLM output
    LLMTotalStatements = "LLMTotalStatements"

    # Number of uninterpreted statements
    LLMUninterpretedStatements = "LLMUninterpretedStatements"

    # The coverage before LLM call for uncovered targets (initial coverage)
    CoverageBeforeLLMCall = "CoverageBeforeLLMCall"

    # The coverage after LLM call for uncovered targets
    CoverageAfterLLMCall = "CoverageAfterLLMCall"

    # Total assertions added to test cases that were received from the LLM
    TotalAssertionsAddedFromLLM = "TotalAssertionsAddedFromLLM"

    # Total assertions added to test cases
    TotalAssertionsReceivedFromLLM = "TotalAssertionsReceivedFromLLM"

    # Discovered non-whitelisted C-extension modules in the SUT
    CExtensionModules = "CExtensionModules"

    # Whether the subprocess mode was used or not
    SubprocessMode = "SubprocessMode"

    def __repr__(self):
        return f"{self.name}"
