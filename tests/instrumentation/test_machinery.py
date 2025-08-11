#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import asyncio
import importlib

from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from tests.utils.version import only_3_10


@only_3_10
def test_hook(subject_properties: SubjectProperties):
    with install_import_hook("tests.fixtures.instrumentation.mixed", subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module("tests.fixtures.instrumentation.mixed")
            importlib.reload(module)

        assert len(subject_properties.existing_code_objects) > 0

        with subject_properties.instrumentation_tracer:
            assert module.function(6) == 0


@only_3_10
def test_module_instrumentation_integration(subject_properties: SubjectProperties):
    """Tests the instrumentation for various function types."""
    with install_import_hook("tests.fixtures.instrumentation.mixed", subject_properties):
        with subject_properties.instrumentation_tracer:
            mixed = importlib.import_module("tests.fixtures.instrumentation.mixed")
            mixed = importlib.reload(mixed)

        with subject_properties.instrumentation_tracer:
            inst = mixed.TestClass(5)
            inst.method(5)
            inst.method_with_nested(5)
            mixed.function(5)
            sum(mixed.generator())
            asyncio.run(mixed.coroutine(5))
            asyncio.run(run_async_generator(mixed.async_generator()))

        assert (
            len(subject_properties.instrumentation_tracer.get_trace().executed_code_objects) == 10
        )


async def run_async_generator(gen):
    """Small helper to execute async generator."""
    the_sum = 0
    async for i in gen:
        the_sum += i
    return the_sum
