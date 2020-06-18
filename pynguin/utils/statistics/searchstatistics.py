# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides a search statistics that collects all the data values reported"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.testsuite.testsuitechromosome as tsc
import pynguin.utils.statistics.outputvariablefactory as ovf
import pynguin.utils.statistics.statistics as stat  # pylint: disable=cyclic-import
import pynguin.utils.statistics.statisticsbackend as sb


class SearchStatistics:
    """A singleton of SearchStatistics collects all the data values reported.

    Because we cannot guarantee a singleton here without making the code too crazy,
    the only instance of this class that shall exist throughout the whole framework
    is in the `StatisticsTracker`.  The `StatisticsTracker` provides public methods
    for all public methods of this class, which delegate to its instance.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self):
        self._backend: Optional[
            sb.AbstractStatisticsBackend
        ] = self._initialise_backend()
        self._output_variables: Dict[str, sb.OutputVariable] = {}
        self._variable_factories: Dict[str, ovf.ChromosomeOutputVariableFactory] = {}
        self._sequence_output_variable_factories: Dict[
            str, ovf.SequenceOutputVariableFactory
        ] = {}
        self._init_factories()
        self.set_output_variable_for_runtime_variable(
            stat.RuntimeVariable.RandomSeed, config.INSTANCE.seed
        )
        self._fill_sequence_output_variable_factories()
        self._start_time = time.time_ns()
        self.set_sequence_output_variable_start_time(self._start_time)
        self._best_individual: Optional[tsc.TestSuiteChromosome] = None

    @staticmethod
    def _initialise_backend() -> Optional[sb.AbstractStatisticsBackend]:
        backend = config.INSTANCE.statistics_backend
        if backend == config.StatisticsBackend.CONSOLE:
            return sb.ConsoleStatisticsBackend()
        if backend == config.StatisticsBackend.CSV:
            return sb.CSVStatisticsBackend()
        return None

    def _init_factories(self) -> None:
        self._variable_factories[
            stat.RuntimeVariable.Length.name
        ] = self._ChromosomeLengthOutputVariableFactory()
        self._variable_factories[
            stat.RuntimeVariable.Size.name
        ] = self._ChromosomeSizeOutputVariableFactory()
        self._variable_factories[
            stat.RuntimeVariable.Coverage.name
        ] = self._ChromosomeCoverageOutputVariableFactory()
        self._variable_factories[
            stat.RuntimeVariable.Fitness.name
        ] = self._ChromosomeFitnessOutputVariableFactory()

    def _fill_sequence_output_variable_factories(self) -> None:
        self._sequence_output_variable_factories[
            stat.RuntimeVariable.CoverageTimeline.name
        ] = self._CoverageSequenceOutputVariableFactory()
        self._sequence_output_variable_factories[
            stat.RuntimeVariable.SizeTimeline.name
        ] = self._SizeSequenceOutputVariableFactory()
        self._sequence_output_variable_factories[
            stat.RuntimeVariable.LengthTimeline.name
        ] = self._LengthSequenceOutputVariableFactory()
        self._sequence_output_variable_factories[
            stat.RuntimeVariable.FitnessTimeline.name
        ] = self._FitnessSequenceOutputVariableFactory()
        self._sequence_output_variable_factories[
            stat.RuntimeVariable.TotalExceptionsTimeline.name
        ] = ovf.DirectSequenceOutputVariableFactory.get_integer(
            stat.RuntimeVariable.TotalExceptionsTimeline
        )

    def set_sequence_output_variable_start_time(self, start_time: int) -> None:
        """Set start time for sequence data.

        Args:
            start_time: the start time
        """
        for factory in self._sequence_output_variable_factories.values():
            factory.set_start_time(start_time)

    def current_individual(self, individual: chrom.Chromosome) -> None:
        """Called when a new individual is sent.

        The individual represents the best individual of the current generation.

        Args:
            individual: The best individual of the current generation
        """
        if not self._backend:
            return

        if not isinstance(individual, tsc.TestSuiteChromosome):
            self._logger.warning("SearchStatistics expected a TestSuiteChromosome")
            return

        self._logger.debug("Received individual")
        self._best_individual = individual
        for variable_factory in self._variable_factories.values():
            self.set_output_variable(variable_factory.get_variable(individual))
        for seq_variable_factory in self._sequence_output_variable_factories.values():
            seq_variable_factory.update(individual)

    def set_output_variable(self, variable: sb.OutputVariable) -> None:
        """Sets an output variable to a value directly

        Args:
            variable: The variable to be set
        """
        if variable.name in self._sequence_output_variable_factories:
            var = self._sequence_output_variable_factories[variable.name]
            assert isinstance(var, ovf.DirectSequenceOutputVariableFactory)
            var.set_value(variable.value)
        else:
            self._output_variables[variable.name] = variable

    def set_output_variable_for_runtime_variable(
        self, variable: stat.RuntimeVariable, value: Any
    ) -> None:
        """Sets an output variable to a value directly

        Args:
            variable: The variable to be set
            value: the value to be set
        """
        self.set_output_variable(sb.OutputVariable(name=variable.name, value=value))

    @property
    def output_variables(self) -> Dict[str, sb.OutputVariable]:
        """Provides the output variables.

        Returns:
            The output variables
        """
        return self._output_variables

    def _get_output_variables(
        self, individual, skip_missing: bool = True
    ) -> Dict[str, sb.OutputVariable]:
        variables: Dict[str, sb.OutputVariable] = {}

        for variable in config.INSTANCE.output_variables:
            variable_name = variable.name
            if variable_name in self._output_variables:
                # Values directly sent
                variables[variable_name] = self._output_variables[variable_name]
            elif variable_name in self._variable_factories:
                # Values extracted from the individual
                variables[variable_name] = self._variable_factories[
                    variable_name
                ].get_variable(individual)
            elif variable_name in self._sequence_output_variable_factories:
                # Time related values, which will be expanded in a list of values
                # through time
                for var in self._sequence_output_variable_factories[
                    variable_name
                ].get_output_variables():
                    variables[var.name] = var
            elif skip_missing:
                # if variable does not exist, return an empty value instead
                variables[variable_name] = sb.OutputVariable(
                    name=variable_name, value=""
                )
            else:
                self._logger.error(
                    "No obtained value for output variable %s", variable_name
                )
                return {}

        return variables

    def write_statistics(self) -> bool:
        """Write result to disk using selected backend

        Returns:
            True if the writing was successful
        """
        self._logger.info("Writing statistics")
        if not self._backend:
            return False

        self._output_variables[stat.RuntimeVariable.TotalTime.name] = sb.OutputVariable(
            name=stat.RuntimeVariable.TotalTime.name,
            value=time.time_ns() - self._start_time,
        )

        if not self._best_individual:
            self._logger.error(
                "No statistics has been saved because Pynguin failed to generate any "
                "test case"
            )
            return False

        individual = self._best_individual
        output_variables = self._get_output_variables(individual)
        self._backend.write_data(output_variables)
        return True

    class _ChromosomeLengthOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.Length)

        def get_data(self, individual: tsc.TestSuiteChromosome) -> int:
            return individual.total_length_of_test_cases

    class _ChromosomeSizeOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.Size)

        def get_data(self, individual: tsc.TestSuiteChromosome) -> int:
            return individual.size()

    class _ChromosomeCoverageOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.Coverage)

        def get_data(self, individual: tsc.TestSuiteChromosome) -> float:
            return individual.get_coverage()

    class _ChromosomeFitnessOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.Fitness)

        def get_data(self, individual: tsc.TestSuiteChromosome) -> float:
            return individual.get_fitness()

    class _CoverageSequenceOutputVariableFactory(
        ovf.DirectSequenceOutputVariableFactory
    ):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.CoverageTimeline, 0.0)

        def get_value(self, individual: tsc.TestSuiteChromosome) -> float:
            return individual.get_coverage()

    class _SizeSequenceOutputVariableFactory(ovf.DirectSequenceOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.SizeTimeline, 0)

        def get_value(self, individual: tsc.TestSuiteChromosome) -> int:
            return individual.size()

    class _LengthSequenceOutputVariableFactory(ovf.DirectSequenceOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.LengthTimeline, 0)

        def get_value(self, individual: tsc.TestSuiteChromosome) -> int:
            return individual.total_length_of_test_cases

    class _FitnessSequenceOutputVariableFactory(
        ovf.DirectSequenceOutputVariableFactory
    ):
        def __init__(self) -> None:
            super().__init__(stat.RuntimeVariable.FitnessTimeline, 0.0)

        def get_value(self, individual: tsc.TestSuiteChromosome) -> float:
            return individual.get_fitness()
