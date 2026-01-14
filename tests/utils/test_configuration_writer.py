#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import logging
import os
from pathlib import Path
from unittest.mock import patch

import pytest

import pynguin.configuration as config
from pynguin.configuration import StatisticsBackend
from pynguin.utils.configuration_writer import (
    PYNGUIN_CONFIG_TOML,
    PYNGUIN_CONFIG_TXT,
    convert_config_to_dict,
    extract_parameter_list_from_config,
    read_config_from_dict,
    write_configuration,
)


@pytest.fixture
def expected_toml(tmp_path):
    expected_toml = Path(tmp_path) / f"expected-{PYNGUIN_CONFIG_TOML}"
    expected = """project_path = ""
module_name = ""
algorithm = "RANDOM"
ignore_modules = []
ignore_methods = []
subprocess = false
subprocess_if_recommended = true
use_master_worker = true
filesystem_isolation = false

[test_case_output]
output_path = ""
crash_path = ""
export_strategy = "PY_TEST"
max_length_test_case = 2500
assertion_generation = "MUTATION_ANALYSIS"
allow_stale_assertions = false
mutation_strategy = "FIRST_ORDER_MUTANTS"
mutation_order = 1
post_process = true
float_precision = 0.01
format_with_black = true

[statistics_output]
report_dir = "{REPORT_DIR}"
statistics_backend = "CSV"
timeline_interval = 1000000000
timeline_interpolation = true
coverage_metrics = [ "BRANCH",]
output_variables = [ "TargetModule", "Coverage",]
configuration_id = ""
run_id = ""
project_name = ""
create_coverage_report = false
type_guess_top_n = 10
store_test_before_execution = false

[stopping]
maximum_search_time = -1
maximum_test_executions = -1
maximum_statement_executions = -1
maximum_slicing_time = 600
maximum_iterations = -1
maximum_test_execution_timeout = 5
maximum_coverage = 100
maximum_coverage_plateau = -1
minimum_coverage = 100
minimum_plateau_iterations = -1
maximum_memory = 3000
test_execution_time_per_statement = 1

[large_language_model]
api_key = ""
model_name = "gpt-4o-mini"
temperature = 0.8
hybrid_initial_population = false
llm_test_case_percentage = 0.5
enable_response_caching = false
call_llm_for_uncovered_targets = false
coverage_threshold = 1
call_llm_on_stall_detection = false
max_plateau_len = 25
max_llm_interventions = 1

[string_statement]
random_string_weight = 0.3
faker_string_weight = 0.3
fandango_string_weight = 0.4
fandango_faker_string_weight = 0.0

[seeding]
seed = {SEED}
constant_seeding = true
initial_population_seeding = false
initial_population_data = ""
seeded_testcases_reuse_probability = 0.9
initial_population_mutations = 0
dynamic_constant_seeding = true
seeded_primitives_reuse_probability = 0.2
seeded_dynamic_values_reuse_probability = 0.6
seed_from_archive = false
seed_from_archive_probability = 0.2
seed_from_archive_mutations = 3
max_dynamic_length = 1000
max_dynamic_pool_size = 50

[type_inference]
type_inference_strategy = "TYPE_HINTS"
type_tracing = 0.0
subtype_inference = "NONE"
type_tracing_subtype_weight = 0.3
type_tracing_argument_type_weight = 0.5
type_tracing_attribute_weight = 0.2
typeevalpy_json_path = ""

[pynguinml]
ml_testing_enabled = false
constraints_path = ""
dtype_mapping_path = ""
constructor_function = ""
constructor_function_parameter = ""
max_ndim = 4
max_shape_dim = 4
ignore_constraints_probability = 0.25

[test_creation]
max_recursion = 10
max_delta = 20
max_int = 2048
string_length = 20
bytes_length = 20
collection_size = 5
primitive_reuse_probability = 0.5
object_reuse_probability = 0.9
none_weight = 0
any_weight = 0
original_type_weight = 5
type_tracing_weight = 10
type_tracing_kept_guesses = 2
wrap_var_param_type_probability = 0.7
negate_type = 0.1
skip_optional_parameter_probability = 0.7
max_attempts = 1000
insertion_uut = 0.5
max_size = 100
use_random_object_for_call = 0.0

[generator_selection]
generator_selection_algorithm = "RANK_SELECTION"
generator_selection_bias = 1.7
generator_any_distance = 30
generator_not_constructor_penalty = 10.0
generator_param_penalty = 1.0
generator_hierarchy_penalty = 1.0
generator_any_type_penalty = 100.0

[search_algorithm]
min_initial_tests = 1
max_initial_tests = 10
population = 10
chromosome_length = 48
chop_max_length = true
elite = 1
crossover_rate = 0.648
test_insertion_probability = 0.1
test_delete_probability = 0.3333333333333333
test_change_probability = 0.3333333333333333
test_insert_probability = 0.3333333333333333
statement_insertion_probability = 0.5
random_perturbation = 0.2
change_parameter_probability = 0.1
tournament_size = 4
rank_bias = 1.68
selection = "RANK_SELECTION"
use_archive = false
filter_covered_targets_from_test_cluster = false
number_of_mutations = 3

[mio]
exploitation_starts_at_percent = 0.5

[random]
max_sequence_length = 10
max_sequences_combined = 10

[to_cover]
only_cover = []
no_cover = []
enable_inline_pynguin_no_cover = true
enable_inline_pragma_no_cover = true

[local_search]
local_search = true
local_search_same_datatype = true
local_search_different_datatype = false
local_search_llm = false
local_search_primitives = true
local_search_collections = false
local_search_complex_objects = false
local_search_probability = 0.02
local_search_time = 5000
ls_int_delta_increasing_factor = 2
ls_string_random_mutation_count = 10
ls_random_parametrized_statement_call_count = 10
ls_max_different_type_mutations = 10
ls_different_type_primitive_probability = 0.3
ls_different_type_collection_probability = 0.3
ls_dict_max_insertions = 10
ls_llm_whole_module = false

[test_case_output.minimization]
test_case_minimization_strategy = "CASE"
test_case_minimization_direction = "BACKWARD"

[mio.initial_config]
number_of_tests_per_target = 10
random_test_or_from_archive_probability = 0.5
number_of_mutations = 1

[mio.focused_config]
number_of_tests_per_target = 1
random_test_or_from_archive_probability = 0.0
number_of_mutations = 10
"""
    expected = expected.replace("{REPORT_DIR}", str(tmp_path))
    expected = expected.replace("{SEED}", str(config.configuration.seeding.seed))
    expected_toml.write_text(expected)
    return expected_toml


@pytest.fixture
def expected_txt(tmp_path):
    expected_txt = Path(tmp_path) / f"expected-{PYNGUIN_CONFIG_TXT}"
    expected = """("Configuration(project_path='', module_name='', "
 "test_case_output=TestCaseOutputConfiguration(output_path='', crash_path='', "
 "export_strategy=<ExportStrategy.PY_TEST: 'PY_TEST'>, "
 'max_length_test_case=2500, '
 'assertion_generation=<AssertionGenerator.MUTATION_ANALYSIS: '
 "'MUTATION_ANALYSIS'>, allow_stale_assertions=False, "
 'mutation_strategy=<MutationStrategy.FIRST_ORDER_MUTANTS: '
 "'FIRST_ORDER_MUTANTS'>, mutation_order=1, post_process=True, "
 'minimization=Minimization(test_case_minimization_strategy=<MinimizationStrategy.CASE: '
 "'CASE'>, test_case_minimization_direction=<MinimizationDirection.BACKWARD: "
 "'BACKWARD'>), float_precision=0.01, format_with_black=True), "
 "algorithm=<Algorithm.RANDOM: 'RANDOM'>, "
 "statistics_output=StatisticsOutputConfiguration(report_dir='{REPORT_DIR}', "
 "statistics_backend=<StatisticsBackend.CSV: 'CSV'>, "
 'timeline_interval=1000000000, timeline_interpolation=True, '
 "coverage_metrics=[<CoverageMetric.BRANCH: 'BRANCH'>], "
 "output_variables=[TargetModule, Coverage], configuration_id='', run_id='', "
 "project_name='', create_coverage_report=False, type_guess_top_n=10, "
 'store_test_before_execution=False), '
 'stopping=StoppingConfiguration(maximum_search_time=-1, '
 'maximum_test_executions=-1, maximum_statement_executions=-1, '
 'maximum_slicing_time=600, maximum_iterations=-1, '
 'maximum_test_execution_timeout=5, maximum_coverage=100, '
 'maximum_coverage_plateau=-1, minimum_coverage=100, '
 'minimum_plateau_iterations=-1, maximum_memory=3000, '
 'test_execution_time_per_statement=1), '
 "large_language_model=LLMConfiguration(api_key='', model_name='gpt-4o-mini', "
 'temperature=0.8, hybrid_initial_population=False, '
 'llm_test_case_percentage=0.5, enable_response_caching=False, '
 'call_llm_for_uncovered_targets=False, coverage_threshold=1, '
 'call_llm_on_stall_detection=False, max_plateau_len=25, '
 'max_llm_interventions=1), '
 'string_statement=StringStatementConfiguration(random_string_weight=0.3, '
 'faker_string_weight=0.3, fandango_string_weight=0.4, '
 'fandango_faker_string_weight=0.0), '
 'seeding=SeedingConfiguration(seed={SEED}, '
 'constant_seeding=True, initial_population_seeding=False, '
 "initial_population_data='', seeded_testcases_reuse_probability=0.9, "
 'initial_population_mutations=0, dynamic_constant_seeding=True, '
 'seeded_primitives_reuse_probability=0.2, '
 'seeded_dynamic_values_reuse_probability=0.6, seed_from_archive=False, '
 'seed_from_archive_probability=0.2, seed_from_archive_mutations=3, '
 'max_dynamic_length=1000, max_dynamic_pool_size=50), '
 'type_inference=TypeInferenceConfiguration(type_inference_strategy=<TypeInferenceStrategy.TYPE_HINTS: '
 "'TYPE_HINTS'>, type_tracing=0.0, "
 "subtype_inference=<SubtypeInferenceStrategy.NONE: 'NONE'>, "
 'type_tracing_subtype_weight=0.3, type_tracing_argument_type_weight=0.5, '
 "type_tracing_attribute_weight=0.2, typeevalpy_json_path=''), "
 'pynguinml=PynguinMLConfiguration(ml_testing_enabled=False, '
 "constraints_path='', dtype_mapping_path='', constructor_function='', "
 "constructor_function_parameter='', max_ndim=4, max_shape_dim=4, "
 'ignore_constraints_probability=0.25), '
 'test_creation=TestCreationConfiguration(max_recursion=10, max_delta=20, '
 'max_int=2048, string_length=20, bytes_length=20, collection_size=5, '
 'primitive_reuse_probability=0.5, object_reuse_probability=0.9, '
 'none_weight=0, any_weight=0, original_type_weight=5, type_tracing_weight=10, '
 'type_tracing_kept_guesses=2, wrap_var_param_type_probability=0.7, '
 'negate_type=0.1, skip_optional_parameter_probability=0.7, max_attempts=1000, '
 'insertion_uut=0.5, max_size=100, use_random_object_for_call=0.0), '
 'generator_selection=GeneratorSelectionConfiguration(generator_selection_algorithm=<Selection.RANK_SELECTION: '
 "'RANK_SELECTION'>, generator_selection_bias=1.7, generator_any_distance=30, "
 'generator_not_constructor_penalty=10.0, generator_param_penalty=1.0, '
 'generator_hierarchy_penalty=1.0, generator_any_type_penalty=100.0), '
 'search_algorithm=SearchAlgorithmConfiguration(min_initial_tests=1, '
 'max_initial_tests=10, population=10, chromosome_length=48, '
 'chop_max_length=True, elite=1, crossover_rate=0.648, '
 'test_insertion_probability=0.1, test_delete_probability=0.3333333333333333, '
 'test_change_probability=0.3333333333333333, '
 'test_insert_probability=0.3333333333333333, '
 'statement_insertion_probability=0.5, random_perturbation=0.2, '
 'change_parameter_probability=0.1, tournament_size=4, rank_bias=1.68, '
 "selection=<Selection.RANK_SELECTION: 'RANK_SELECTION'>, use_archive=False, "
 'filter_covered_targets_from_test_cluster=False, number_of_mutations=3), '
 'mio=MIOConfiguration(initial_config=MIOPhaseConfiguration(number_of_tests_per_target=10, '
 'random_test_or_from_archive_probability=0.5, number_of_mutations=1), '
 'focused_config=MIOPhaseConfiguration(number_of_tests_per_target=1, '
 'random_test_or_from_archive_probability=0.0, number_of_mutations=10), '
 'exploitation_starts_at_percent=0.5), '
 'random=RandomConfiguration(max_sequence_length=10, '
 'max_sequences_combined=10), to_cover=ToCoverConfiguration(only_cover=[], '
 'no_cover=[], enable_inline_pynguin_no_cover=True, '
 'enable_inline_pragma_no_cover=True), ignore_modules=[], ignore_methods=[], '
 'subprocess=False, subprocess_if_recommended=True, '
 'local_search=LocalSearchConfiguration(local_search=True, '
 'local_search_same_datatype=True, local_search_different_datatype=False, '
 'local_search_llm=False, local_search_primitives=True, '
 'local_search_collections=False, local_search_complex_objects=False, '
 'local_search_probability=0.02, local_search_time=5000, '
 'ls_int_delta_increasing_factor=2, ls_string_random_mutation_count=10, '
 'ls_random_parametrized_statement_call_count=10, '
 'ls_max_different_type_mutations=10, '
 'ls_different_type_primitive_probability=0.3, '
 'ls_different_type_collection_probability=0.3, ls_dict_max_insertions=10, '
 'ls_llm_whole_module=False), use_master_worker=True, '
 'filesystem_isolation=False)')"""  # noqa:E501
    expected = expected.replace("{REPORT_DIR}", str(tmp_path))
    expected = expected.replace("{SEED}", str(config.configuration.seeding.seed))
    expected_txt.write_text(expected)
    return expected_txt


@pytest.fixture
def expected_parameters() -> str:
    return """--algorithm
RANDOM
--filesystem_isolation
False
--generator_selection.generator_any_distance
30
--generator_selection.generator_any_type_penalty
100.0
--generator_selection.generator_hierarchy_penalty
1.0
--generator_selection.generator_not_constructor_penalty
10.0
--generator_selection.generator_param_penalty
1.0
--generator_selection.generator_selection_algorithm
RANK_SELECTION
--generator_selection.generator_selection_bias
1.7
--large_language_model.call_llm_for_uncovered_targets
False
--large_language_model.call_llm_on_stall_detection
False
--large_language_model.coverage_threshold
1
--large_language_model.enable_response_caching
False
--large_language_model.hybrid_initial_population
False
--large_language_model.llm_test_case_percentage
0.5
--large_language_model.max_llm_interventions
1
--large_language_model.max_plateau_len
25
--large_language_model.model_name
gpt-4o-mini
--large_language_model.temperature
0.8
--local_search.local_search
True
--local_search.local_search_collections
False
--local_search.local_search_complex_objects
False
--local_search.local_search_different_datatype
False
--local_search.local_search_llm
False
--local_search.local_search_primitives
True
--local_search.local_search_probability
0.02
--local_search.local_search_same_datatype
True
--local_search.local_search_time
5000
--local_search.ls_dict_max_insertions
10
--local_search.ls_different_type_collection_probability
0.3
--local_search.ls_different_type_primitive_probability
0.3
--local_search.ls_int_delta_increasing_factor
2
--local_search.ls_llm_whole_module
False
--local_search.ls_max_different_type_mutations
10
--local_search.ls_random_parametrized_statement_call_count
10
--local_search.ls_string_random_mutation_count
10
--mio.exploitation_starts_at_percent
0.5
--mio.focused_config.number_of_mutations
10
--mio.focused_config.number_of_tests_per_target
1
--mio.focused_config.random_test_or_from_archive_probability
0.0
--mio.initial_config.number_of_mutations
1
--mio.initial_config.number_of_tests_per_target
10
--mio.initial_config.random_test_or_from_archive_probability
0.5
--module_name
dummy
--project_path
/tmp
--pynguinml.ignore_constraints_probability
0.25
--pynguinml.max_ndim
4
--pynguinml.max_shape_dim
4
--pynguinml.ml_testing_enabled
False
--random.max_sequence_length
10
--random.max_sequences_combined
10
--search_algorithm.change_parameter_probability
0.1
--search_algorithm.chop_max_length
True
--search_algorithm.chromosome_length
48
--search_algorithm.crossover_rate
0.648
--search_algorithm.elite
1
--search_algorithm.filter_covered_targets_from_test_cluster
False
--search_algorithm.max_initial_tests
10
--search_algorithm.min_initial_tests
1
--search_algorithm.number_of_mutations
3
--search_algorithm.population
10
--search_algorithm.random_perturbation
0.2
--search_algorithm.rank_bias
1.68
--search_algorithm.selection
RANK_SELECTION
--search_algorithm.statement_insertion_probability
0.5
--search_algorithm.test_change_probability
0.3333333333333333
--search_algorithm.test_delete_probability
0.3333333333333333
--search_algorithm.test_insert_probability
0.3333333333333333
--search_algorithm.test_insertion_probability
0.1
--search_algorithm.tournament_size
4
--search_algorithm.use_archive
False
--seeding.constant_seeding
True
--seeding.dynamic_constant_seeding
True
--seeding.initial_population_mutations
0
--seeding.initial_population_seeding
False
--seeding.max_dynamic_length
1000
--seeding.max_dynamic_pool_size
50
--seeding.seed
12345
--seeding.seed_from_archive
False
--seeding.seed_from_archive_mutations
3
--seeding.seed_from_archive_probability
0.2
--seeding.seeded_dynamic_values_reuse_probability
0.6
--seeding.seeded_primitives_reuse_probability
0.2
--seeding.seeded_testcases_reuse_probability
0.9
--statistics_output.coverage_metrics
BRANCH
--statistics_output.create_coverage_report
False
--statistics_output.output_variables
TargetModule
Coverage
--statistics_output.report_dir
pynguin-report
--statistics_output.statistics_backend
CSV
--statistics_output.store_test_before_execution
False
--statistics_output.timeline_interpolation
True
--statistics_output.timeline_interval
1000000000
--statistics_output.type_guess_top_n
10
--stopping.maximum_coverage
100
--stopping.maximum_coverage_plateau
-1
--stopping.maximum_iterations
-1
--stopping.maximum_memory
3000
--stopping.maximum_search_time
-1
--stopping.maximum_slicing_time
600
--stopping.maximum_statement_executions
-1
--stopping.maximum_test_execution_timeout
5
--stopping.maximum_test_executions
-1
--stopping.minimum_coverage
100
--stopping.minimum_plateau_iterations
-1
--stopping.test_execution_time_per_statement
1
--string_statement.faker_string_weight
0.3
--string_statement.fandango_faker_string_weight
0.0
--string_statement.fandango_string_weight
0.4
--string_statement.random_string_weight
0.3
--subprocess
False
--subprocess_if_recommended
True
--test_case_output.allow_stale_assertions
False
--test_case_output.assertion_generation
MUTATION_ANALYSIS
--test_case_output.export_strategy
PY_TEST
--test_case_output.float_precision
0.01
--test_case_output.format_with_black
True
--test_case_output.max_length_test_case
2500
--test_case_output.minimization.test_case_minimization_direction
BACKWARD
--test_case_output.minimization.test_case_minimization_strategy
CASE
--test_case_output.mutation_order
1
--test_case_output.mutation_strategy
FIRST_ORDER_MUTANTS
--test_case_output.post_process
True
--test_creation.any_weight
0
--test_creation.bytes_length
20
--test_creation.collection_size
5
--test_creation.insertion_uut
0.5
--test_creation.max_attempts
1000
--test_creation.max_delta
20
--test_creation.max_int
2048
--test_creation.max_recursion
10
--test_creation.max_size
100
--test_creation.negate_type
0.1
--test_creation.none_weight
0
--test_creation.object_reuse_probability
0.9
--test_creation.original_type_weight
5
--test_creation.primitive_reuse_probability
0.5
--test_creation.skip_optional_parameter_probability
0.7
--test_creation.string_length
20
--test_creation.type_tracing_kept_guesses
2
--test_creation.type_tracing_weight
10
--test_creation.use_random_object_for_call
0.0
--test_creation.wrap_var_param_type_probability
0.7
--to_cover.enable_inline_pragma_no_cover
True
--to_cover.enable_inline_pynguin_no_cover
True
--type_inference.subtype_inference
NONE
--type_inference.type_inference_strategy
TYPE_HINTS
--type_inference.type_tracing
0.0
--type_inference.type_tracing_argument_type_weight
0.5
--type_inference.type_tracing_attribute_weight
0.2
--type_inference.type_tracing_subtype_weight
0.3
--use_master_worker
True"""


def expected_parameter_list() -> list[str]:
    parameter_list: list[str] = [
        "--project_path /tmp",
        "--module_name dummy",
        "--export_strategy PY_TEST",
        "--max_length_test_case 2500",
        "--assertion_generation MUTATION_ANALYSIS",
        "--allow_stale_assertions False",
        "--any_weight 0",
        "--mutation_strategy FIRST_ORDER_MUTANTS",
        "--mutation_order 1",
        "--post_process True",
        "--minimization.test_case_minimization_direction BACKWARD",
        "--minimization.test_case_minimization_strategy CASE",
        "--float_precision 0.01",
        "--format_with_black True",
        "--algorithm RANDOM",  # as defined in tests/conftest.py
        "--report_dir pynguin-report",
        "--statistics_backend CSV",
        "--timeline_interval 1000000000",
        "--timeline_interpolation True",
        "--coverage_metrics BRANCH",
        "--output_variables TargetModule\nCoverage",
        "--create_coverage_report False",
        "--type_guess_top_n 10",
        "--maximum_search_time -1",
        "--maximum_test_executions -1",
        "--maximum_statement_executions -1",
        "--maximum_slicing_time 600",
        "--maximum_iterations -1",
        "--maximum_memory 3000",
        "--maximum_test_execution_timeout 5",
        "--maximum_coverage 100",
        "--maximum_coverage_plateau -1",
        "--minimum_coverage 100",
        "--minimum_plateau_iterations -1",
        "--ml_testing_enabled False",
        "--test_execution_time_per_statement 1",
        "--seed 12345",
        "--constant_seeding True",
        "--initial_population_seeding False",
        "--seeded_testcases_reuse_probability 0.9",
        "--initial_population_mutations 0",
        "--dynamic_constant_seeding True",
        "--seeded_primitives_reuse_probability 0.2",
        "--seeded_dynamic_values_reuse_probability 0.6",
        "--seed_from_archive False",
        "--seed_from_archive_probability 0.2",
        "--seed_from_archive_mutations 3",
        "--max_dynamic_length 1000",
        "--max_dynamic_pool_size 50",
        "--type_inference_strategy TYPE_HINTS",
        "--type_tracing 0.0",
        "--max_recursion 10",
        "--max_delta 20",
        "--max_int 2048",
        "--string_length 20",
        "--subprocess False",
        "--subprocess_if_recommended True",
        "--subtype_inference NONE",
        "--bytes_length 20",
        "--collection_size 5",
        "--primitive_reuse_probability 0.5",
        "--object_reuse_probability 0.9",
        "--none_weight 0",
        "--original_type_weight 5",
        "--type_tracing_weight 10",
        "--type_tracing_argument_type_weight 0.5",
        "--type_tracing_attribute_weight 0.2",
        "--type_tracing_kept_guesses 2",
        "--type_tracing_subtype_weight 0.3",
        "--wrap_var_param_type_probability 0.7",
        "--negate_type 0.1",
        "--skip_optional_parameter_probability 0.7",
        "--max_attempts 1000",
        "--insertion_uut 0.5",
        "--max_size 100",
        "--use_random_object_for_call 0.0",
        "--min_initial_tests 1",
        "--max_initial_tests 10",
        "--population 10",
        "--chromosome_length 48",
        "--chop_max_length True",
        "--elite 1",
        "--enable_inline_pragma_no_cover True",
        "--enable_inline_pynguin_no_cover True",
        "--crossover_rate 0.648",
        "--test_insertion_probability 0.1",
        "--test_delete_probability 0.3333333333333333",
        "--test_change_probability 0.3333333333333333",
        "--test_insert_probability 0.3333333333333333",
        "--statement_insertion_probability 0.5",
        "--random_perturbation 0.2",
        "--change_parameter_probability 0.1",
        "--tournament_size 4",
        "--rank_bias 1.68",
        "--selection RANK_SELECTION",
        "--generator_selection_algorithm RANK_SELECTION",
        "--generator_selection_bias 1.7",
        "--generator_any_distance 30",
        "--generator_not_constructor_penalty 10.0",
        "--generator_param_penalty 1.0",
        "--generator_hierarchy_penalty 1.0",
        "--generator_any_type_penalty 100.0",
        "--use_archive False",
        "--filter_covered_targets_from_test_cluster False",
        "--number_of_mutations 3",
        "--exploitation_starts_at_percent 0.5",
        "--initial_config.number_of_tests_per_target 10",
        "--initial_config.random_test_or_from_archive_probability 0.5",
        "--initial_config.number_of_mutations 1",
        "--focused_config.number_of_tests_per_target 1",
        "--focused_config.random_test_or_from_archive_probability 0.0",
        "--focused_config.number_of_mutations 10",
        "--max_sequence_length 10",
        "--max_sequences_combined 10",
        "--model_name gpt-4o-mini",
        "--temperature 0.8",
        "--hybrid_initial_population False",
        "--random_string_weight 0.3",
        "--faker_string_weight 0.3",
        "--fandango_string_weight 0.4",
        "--fandango_faker_string_weight 0.0",
        "--llm_test_case_percentage 0.5",
        "--enable_response_caching False",
        "--call_llm_for_uncovered_targets False",
        "--coverage_threshold 1",
        "--call_llm_on_stall_detection False",
        "--max_plateau_len 25",
        "--max_llm_interventions 1",
        "--max_ndim 4",
        "--max_shape_dim 4",
        "--ignore_constraints_probability 0.25",
        "--api_key " + os.getenv("OPENAI_API_KEY", ""),
        "--ls_dict_max_insertions 10",
        "--ls_different_type_collection_probability 0.3",
        "--ls_different_type_primitive_probability 0.3",
        "--ls_int_delta_increasing_factor 2",
        "--ls_llm_whole_module False",
        "--local_search True",
        "--local_search_collections False",
        "--local_search_complex_objects False",
        "--local_search_different_datatype False",
        "--local_search_llm False",
        "--local_search_primitives True",
        "--local_search_probability 0.02",
        "--local_search_same_datatype True",
        "--local_search_time 5000",
        "--ls_max_different_type_mutations 10",
        "--ls_random_parametrized_statement_call_count 10",
        "--ls_string_random_mutation_count 10",
    ]
    return sorted(parameter_list)


def test_write_configuration(expected_toml, expected_txt, tmp_path):
    config.configuration.statistics_output.statistics_backend = StatisticsBackend.CSV
    config.configuration.statistics_output.report_dir = str(tmp_path)

    write_configuration()

    toml_path = Path(config.configuration.statistics_output.report_dir) / PYNGUIN_CONFIG_TOML
    assert toml_path.exists()
    assert toml_path.read_text() == expected_toml.read_text()

    txt_path = Path(config.configuration.statistics_output.report_dir) / PYNGUIN_CONFIG_TXT
    assert txt_path.exists()
    assert txt_path.read_text() == expected_txt.read_text()


@pytest.mark.parametrize(
    "input_value, expected_output",
    [
        ({"key": "value"}, {"key": "value"}),
        (["item1", "item2"], ["item1", "item2"]),
        (StatisticsBackend.CSV, "CSV"),
        (123, 123),
        ("string", "string"),
        (None, None),
    ],
)
def test_convert_config_to_dict(input_value, expected_output):
    assert convert_config_to_dict(input_value) == expected_output


def test_convert_object_with_dict():
    class CustomConfig:
        def __init__(self):
            self.option = "value"

    obj = CustomConfig()
    expected_output = {"option": "value"}

    assert convert_config_to_dict(obj) == expected_output


def test_read_config_from_dict_none_instance():
    test_input = {"unknown_key": "some_value"}
    with pytest.raises(ValueError, match="Could not construct dataclass from dictionary"):
        read_config_from_dict(test_input)


def test_convert_forth_and_back():
    config_dict = convert_config_to_dict(config.configuration)
    read_config = read_config_from_dict(config_dict)
    assert config.configuration == read_config


def test_ignore_callable_and_dunder_methods():
    class Sample:
        def __init__(self):
            self.visible = "yes"
            self._hidden = "no"
            self.__private = "secret"

        def method(self):
            return "should be ignored"

    sample_obj = Sample()
    converted = convert_config_to_dict(sample_obj)

    assert "visible" in converted
    assert "_hidden" in converted
    assert "__private" not in converted
    assert "method" not in converted


def test_extract_parameter_list_from_config(expected_parameters):
    config.configuration.module_name = "dummy"
    config.configuration.project_path = "/tmp"  # noqa: S108
    config.configuration.seeding.seed = 12345

    parameter_list = extract_parameter_list_from_config(verbosity=False)

    assert "\n".join(parameter_list) == expected_parameters


def test_extract_parameter_list_from_config_preserve_verbosity():
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        mock_logger.getEffectiveLevel.return_value = logging.DEBUG  # Simulate verbose logging
        parameter_list = extract_parameter_list_from_config()
        assert "-v" not in parameter_list


@pytest.mark.parametrize(
    "log_level, expected_v_flag",
    [
        (logging.INFO, "-v"),
        (logging.DEBUG, "-vv"),
    ],
)
def test_extract_parameter_list_from_config_preserve_verbosity_2(log_level, expected_v_flag):
    with patch("logging.getLogger") as mock_get_logger:
        mock_logger = mock_get_logger.return_value
        mock_logger.getEffectiveLevel.return_value = log_level

        parameter_list = extract_parameter_list_from_config()

        assert expected_v_flag in parameter_list
