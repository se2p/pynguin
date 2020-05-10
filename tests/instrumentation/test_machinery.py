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

        assert len(tracer.get_trace().covered_code_objects) == 10


async def run_async_generator(gen):
    """Small helper to execute async generator"""
    the_sum = 0
    async for i in gen:
        the_sum += i
    return the_sum
