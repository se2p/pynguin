#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import asyncio
import importlib

from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution.executiontracer import ExecutionTracer


def test_hook():
    tracer = ExecutionTracer()
    with install_import_hook("tests.fixtures.instrumentation.mixed", tracer):
        module = importlib.import_module("tests.fixtures.instrumentation.mixed")
        importlib.reload(module)
        assert len(tracer.get_known_data().existing_code_objects) > 0
        assert module.function(6) == 0


def test_module_instrumentation_integration():
    """Small integration test, which tests the instrumentation for various function types."""
    tracer = ExecutionTracer()
    with install_import_hook("tests.fixtures.instrumentation.mixed", tracer):
        mixed = importlib.import_module("tests.fixtures.instrumentation.mixed")
        mixed = importlib.reload(mixed)

        inst = mixed.TestClass(5)
        inst.method(5)
        inst.method_with_nested(5)
        mixed.function(5)
        sum(mixed.generator())
        asyncio.run(mixed.coroutine(5))
        asyncio.run(run_async_generator(mixed.async_generator()))

        assert len(tracer.get_trace().executed_code_objects) == 10


async def run_async_generator(gen):
    """Small helper to execute async generator"""
    the_sum = 0
    async for i in gen:
        the_sum += i
    return the_sum
