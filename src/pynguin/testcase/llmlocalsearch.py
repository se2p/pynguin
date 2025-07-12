#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Gives access to local search with LLMs"""
import logging

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.variablereference import VariableReference
from pynguin.utils.mirror import Mirror
from tests.utils.stats.test_searchstatistics import chromosome


class LLMLocalSearch:
    """Provides access to local search using LLMs"""

    _logger = logging.getLogger(__name__)

    def __init__(self, chromosome: TestCaseChromosome, objective: LocalSearchObjective):
        """Initializes the class

        Args:
            chromosome (TestCaseChromosome): The test case which should be changed.
            objective (LocalSearchObjective): The objective which checks if improvements are made.
        """
        self.chromosome = chromosome
        self.objective = objective

    def llm_local_search(self, position):
        """Starts local search using LLMs for the statement at the position.

        Args:
            position (int): The position of the statement in the test case.
        """
        statement = self.chromosome.test_case.statements[position]
        memo :dict[VariableReference, VariableReference] = {}
        old_statement = statement.clone(self.chromosome.test_case, Mirror())
        last_execution_result = self.chromosome.get_last_execution_result()

        agent = LLMAgent()
        output = agent.local_search_call(position=position, test_case_source_code=unparse_test_case(
            self.chromosome.test_case))
        self._logger.debug(output)
        #TODO:PARSE INPUT

        if self.objective.has_improved(self.chromosome):
            self._logger.debug("The llm request has improved the fitness of the test case")
        else:
            self.chromosome.test_case.statements[position] = old_statement
            self.chromosome.set_last_execution_result(last_execution_result)
            self._logger.debug("The llm request hasn't improved the fitness of the test case, "
                               "reverting to the old test case")
