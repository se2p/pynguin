#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides tracking of statistics for various variables and types."""

from __future__ import annotations

import json
import logging
import queue
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.utils.statistics.outputvariablefactory as ovf
import pynguin.utils.statistics.statisticsbackend as sb
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Generator


class _StatisticsTracker:
    """A singleton tracker for statistics."""

    def __init__(self) -> None:
        self._variables: queue.Queue = queue.Queue()
        self._search_statistics: _SearchStatistics = _SearchStatistics()

    def reset(self) -> None:
        """Reset the tracker (necessary for testing only)."""
        self._variables = queue.Queue()
        self._search_statistics = _SearchStatistics()

    def track_output_variable(self, runtime_variable: RuntimeVariable, value: Any):
        """Tracks a run-time variable for output.

        Args:
            runtime_variable: The run-time variable
            value: The value to track for the variable
        """
        self._variables.put((runtime_variable, value))

    @property
    def variables(self) -> queue.Queue:
        """Provides the queue of tracked variables.

        Returns:
            The queue of tracked variables
        """
        return self._variables

    @property
    def variables_generator(self) -> Generator[tuple[RuntimeVariable, Any]]:
        """Provides a generator.

        Yields:
            A generator for iteration
        """
        while not self._variables.empty():
            yield self._variables.get()

    @property
    def search_statistics(self) -> _SearchStatistics:
        """Provides the internal search statistics instance.

        Returns:
            The search statistics instance
        """
        return self._search_statistics

    def set_sequence_start_time(self, start_time: int) -> None:
        """This should only be called once, before any sequence data was generated.

        Args:
            start_time: the start time
        """
        self._search_statistics.set_sequence_output_variable_start_time(start_time)

    def current_individual(self, individual: chrom.Chromosome) -> None:
        """Called when a new individual is sent.

        The individual represents the best individual of the current generation.

        Args:
            individual: The best individual of the current generation
        """
        self._search_statistics.current_individual(individual)

    def set_output_variable(self, variable: sb.OutputVariable) -> None:
        """Sets an output variable to a value directly.

        Args:
            variable: The variable to be set
        """
        self._search_statistics.set_output_variable(variable)

    def update_output_variable(self, variable: sb.OutputVariable) -> None:
        """Updates an output variable with a value.

        Args:
            variable: The variable to update
        """
        self._search_statistics.update_output_variable(variable)

    def set_output_variable_for_runtime_variable(
        self, variable: RuntimeVariable, value: Any
    ) -> None:
        """Sets an output variable to a value directly.

        Args:
            variable: The variable to be set
            value: the value to be set
        """
        self._search_statistics.set_output_variable_for_runtime_variable(variable, value)

    def update_output_variable_for_runtime_variable(
        self, variable: RuntimeVariable, value: Any
    ) -> None:
        """Updates an output variable with a value directly.

        Args:
            variable: The variable to update
            value: The value to add
        """
        self._search_statistics.update_output_variable_for_runtime_variable(variable, value)

    @property
    def output_variables(self) -> dict[str, sb.OutputVariable]:
        """Provides the output variables.

        Returns:
            The output variables
        """
        return self._search_statistics.output_variables

    def write_statistics(self) -> bool:
        """Write result to disk using selected backend.

        Returns:
            True if the writing was successful
        """
        return self._search_statistics.write_statistics()

    def add_to_runtime_variable(self, variable: RuntimeVariable, value: Any) -> None:
        """Adds a value to a runtime variable, assuming it is numeric.

        Args:
            variable: The variable to update
            value: The value to add
        """
        self.search_statistics.add_to_runtime_variable(variable, value)


class _SearchStatistics:
    """A singleton of SearchStatistics collects all the data values reported.

    Because we cannot guarantee a singleton here without making the code too crazy,
    the only instance of this class that shall exist throughout the whole framework
    is in the `StatisticsTracker`.  The `StatisticsTracker` provides public methods
    for all public methods of this class, which delegate to its instance.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self):
        self._backend: sb.AbstractStatisticsBackend | None = self._initialise_backend()
        self._output_variables: dict[str, sb.OutputVariable] = {}
        self._variable_factories: dict[str, ovf.ChromosomeOutputVariableFactory] = {}
        self._sequence_output_variable_factories: dict[str, ovf.SequenceOutputVariableFactory] = {}
        self._init_factories()
        self.set_output_variable_for_runtime_variable(
            RuntimeVariable.RandomSeed, config.configuration.seeding.seed
        )
        self._fill_sequence_output_variable_factories()
        self._start_time = time.time_ns()
        self.set_sequence_output_variable_start_time(self._start_time)
        self._best_individual: chrom.Chromosome | None = None

    @staticmethod
    def _initialise_backend() -> sb.AbstractStatisticsBackend | None:
        backend = config.configuration.statistics_output.statistics_backend
        if backend == config.StatisticsBackend.CONSOLE:
            return sb.ConsoleStatisticsBackend()
        if backend == config.StatisticsBackend.CSV:
            return sb.CSVStatisticsBackend()
        return None

    def _init_factories(self) -> None:
        self._variable_factories[RuntimeVariable.Length.name] = (
            self._ChromosomeLengthOutputVariableFactory()
        )
        self._variable_factories[RuntimeVariable.Size.name] = (
            self._ChromosomeSizeOutputVariableFactory()
        )
        self._variable_factories[RuntimeVariable.Coverage.name] = (
            self._ChromosomeCoverageOutputVariableFactory()
        )
        self._variable_factories[RuntimeVariable.Fitness.name] = (
            self._ChromosomeFitnessOutputVariableFactory()
        )

    def _fill_sequence_output_variable_factories(self) -> None:
        self._sequence_output_variable_factories[RuntimeVariable.CoverageTimeline.name] = (
            self._CoverageSequenceOutputVariableFactory()
        )
        self._sequence_output_variable_factories[RuntimeVariable.SizeTimeline.name] = (
            self._SizeSequenceOutputVariableFactory()
        )
        self._sequence_output_variable_factories[RuntimeVariable.LengthTimeline.name] = (
            self._LengthSequenceOutputVariableFactory()
        )
        self._sequence_output_variable_factories[RuntimeVariable.FitnessTimeline.name] = (
            self._FitnessSequenceOutputVariableFactory()
        )
        self._sequence_output_variable_factories[RuntimeVariable.TotalExceptionsTimeline.name] = (
            ovf.DirectSequenceOutputVariableFactory.get_integer(
                RuntimeVariable.TotalExceptionsTimeline
            )
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

        if not isinstance(individual, chrom.Chromosome):
            self._logger.warning("SearchStatistics expected a TestSuiteChromosome")
            return

        self._logger.debug("Received individual")
        self._best_individual = individual
        for variable_factory in self._variable_factories.values():
            self.set_output_variable(variable_factory.get_variable(individual))
        for seq_variable_factory in self._sequence_output_variable_factories.values():
            seq_variable_factory.update(individual)

    def set_output_variable(self, variable: sb.OutputVariable) -> None:
        """Sets an output variable to a value directly.

        Args:
            variable: The variable to be set
        """
        if variable.name in self._sequence_output_variable_factories:
            var = self._sequence_output_variable_factories[variable.name]
            assert isinstance(var, ovf.DirectSequenceOutputVariableFactory)
            var.set_value(variable.value)
        else:
            self._output_variables[variable.name] = variable

    def update_output_variable(self, variable: sb.OutputVariable) -> None:
        """Updates an output variable with a new value.

        Args:
            variable: The variable to update
        """
        if variable.name not in self._sequence_output_variable_factories:
            raise AssertionError("Can only be called on sequence variable.")
        var = self._sequence_output_variable_factories[variable.name]
        assert isinstance(var, ovf.DirectSequenceOutputVariableFactory)
        var.update_value(variable.value)

    def set_output_variable_for_runtime_variable(
        self, variable: RuntimeVariable, value: Any
    ) -> None:
        """Sets an output variable to a value directly.

        Args:
            variable: The variable to be set
            value: the value to be set
        """
        self.set_output_variable(sb.OutputVariable(name=variable.name, value=value))

    def update_output_variable_for_runtime_variable(
        self, variable: RuntimeVariable, value: Any
    ) -> None:
        """Updates an output variable with a new value.

        Args:
            variable: The variable to update
            value: The value to add
        """
        self.update_output_variable(sb.OutputVariable(name=variable.name, value=value))

    @property
    def output_variables(self) -> dict[str, sb.OutputVariable]:
        """Provides the output variables.

        Returns:
            The output variables
        """
        return self._output_variables

    def _get_output_variables(
        self, individual, *, skip_missing: bool = True
    ) -> dict[str, sb.OutputVariable]:
        output_variables_map: dict[str, sb.OutputVariable] = {}

        for variable in config.configuration.statistics_output.output_variables:
            variable_name = variable.name if hasattr(variable, "name") else str(variable)
            if variable_name in self._output_variables:
                # Values directly sent
                output_variables_map[variable_name] = self._output_variables[variable_name]
            elif variable_name in self._variable_factories:
                # Values extracted from the individual
                output_variables_map[variable_name] = self._variable_factories[
                    variable_name
                ].get_variable(individual)
            elif variable_name in self._sequence_output_variable_factories:
                # Time related values, which will be expanded in a list of values
                # through time
                assert config.configuration.stopping.maximum_search_time >= 0, (
                    "Tracking sequential variables is only possible when using "
                    "maximum search time as a stopping condition"
                )
                for var in self._sequence_output_variable_factories[
                    variable_name
                ].get_output_variables():
                    output_variables_map[var.name] = var

                # For every time-series variable, we compute the area under curve, too
                auc_variable = self._sequence_output_variable_factories[
                    variable_name
                ].area_under_curve_output_variable
                output_variables_map[auc_variable.name] = auc_variable
                # Additionally, add a normalised version of the area under curve
                norm_auc_variable = self._sequence_output_variable_factories[
                    variable_name
                ].normalised_area_under_curve_output_variable
                output_variables_map[norm_auc_variable.name] = norm_auc_variable
            elif skip_missing:
                # if variable does not exist, return an empty value instead
                output_variables_map[variable_name] = sb.OutputVariable(
                    name=variable_name, value=""
                )
            else:
                self._logger.error("No obtained value for output variable %s", variable_name)
                return {}

        return output_variables_map

    def write_statistics(self) -> bool:
        """Write result to disk using selected backend.

        Returns:
            True if the writing was successful
        """
        self._logger.info("Writing statistics")
        # reinitialise backend to be sure we got the correct one, prone to failure
        # due to global-object pattern otherwise.
        self._backend = self._initialise_backend()
        if not self._backend:
            return False

        self._output_variables[RuntimeVariable.TotalTime.name] = sb.OutputVariable(
            name=RuntimeVariable.TotalTime.name,
            value=time.time_ns() - self._start_time,
        )

        if not self._best_individual:
            self._logger.error(
                "No statistics has been saved because Pynguin failed to generate any test case"
            )
            return False

        individual = self._best_individual
        output_variables_map = self._get_output_variables(individual)
        self._backend.write_data(output_variables_map)

        if (
            config.configuration.statistics_output.statistics_backend
            == config.StatisticsBackend.CSV
        ):
            report_dir = Path(config.configuration.statistics_output.report_dir).resolve()
            if "SignatureInfos" in output_variables_map:
                try:
                    obj = json.loads(output_variables_map["SignatureInfos"].value)
                    output_file = report_dir / "signature-infos.json"
                    with output_file.open(mode="w") as f:
                        json.dump(obj, f)
                except json.JSONDecodeError:
                    self._logger.error("Failed to parse signature infos")
        return True

    def add_to_runtime_variable(self, variable: RuntimeVariable, value: Any) -> None:
        """Adds a value to a runtime variable, assuming it is numeric.

        Args:
            variable: The variable to update
            value: The value to add
        """
        old_value = self.output_variables.get(variable.name)
        self.set_output_variable_for_runtime_variable(
            variable,
            old_value.value + value if old_value is not None else value,
        )

    class _ChromosomeLengthOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.Length)

        def get_data(self, individual: chrom.Chromosome) -> int:
            return individual.length()

    class _ChromosomeSizeOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.Size)

        def get_data(self, individual: chrom.Chromosome) -> int:
            return individual.size()

    class _ChromosomeCoverageOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.Coverage)

        def get_data(self, individual: chrom.Chromosome) -> float:
            return individual.get_coverage()

    class _ChromosomeFitnessOutputVariableFactory(ovf.ChromosomeOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.Fitness)

        def get_data(self, individual: chrom.Chromosome) -> float:
            return individual.get_fitness()

    class _CoverageSequenceOutputVariableFactory(ovf.DirectSequenceOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.CoverageTimeline, 0.0)

        def get_value(self, individual: chrom.Chromosome) -> float:
            return individual.get_coverage()

    class _SizeSequenceOutputVariableFactory(ovf.DirectSequenceOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.SizeTimeline, 0)

        def get_value(self, individual: chrom.Chromosome) -> int:
            return individual.size()

    class _LengthSequenceOutputVariableFactory(ovf.DirectSequenceOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.LengthTimeline, 0)

        def get_value(self, individual: chrom.Chromosome) -> int:
            return individual.length()

    class _FitnessSequenceOutputVariableFactory(ovf.DirectSequenceOutputVariableFactory):
        def __init__(self) -> None:
            super().__init__(RuntimeVariable.FitnessTimeline, 0.0)

        def get_value(self, individual: chrom.Chromosome) -> float:
            return individual.get_fitness()


statistics_tracker = _StatisticsTracker()
track_output_variable = statistics_tracker.track_output_variable
variables = statistics_tracker.variables
variables_generator = statistics_tracker.variables_generator
search_statistics = statistics_tracker.search_statistics
set_sequence_start_time = statistics_tracker.set_sequence_start_time
current_individual = statistics_tracker.current_individual
set_output_variable = statistics_tracker.set_output_variable
set_output_variable_for_runtime_variable = (
    statistics_tracker.set_output_variable_for_runtime_variable
)
update_output_variable = search_statistics.update_output_variable
update_output_variable_for_runtime_variable = (
    search_statistics.update_output_variable_for_runtime_variable
)
output_variables = statistics_tracker.output_variables
write_statistics = statistics_tracker.write_statistics
reset = statistics_tracker.reset
add_to_runtime_variable = statistics_tracker.add_to_runtime_variable
