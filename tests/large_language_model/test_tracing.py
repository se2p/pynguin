#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the structured LLM call trace, call statistics and repair during search."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.large_language_model.client import OpenAIClient
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.llmtestcasehandler import (
    ChromosomeContext,
    LLMGeneration,
    LLMTestCaseHandler,
    reset_statement_ratio,
)
from pynguin.large_language_model.prompts.conversationrepairprompt import (
    ConversationRepairPrompt,
)
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.request import RenderedRequest
from pynguin.large_language_model.tracing import (
    TRACE_FILE_NAME,
    CallOutcome,
    CallUsage,
    LLMCallRecord,
    track_outcome,
    write_record,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

_SUT = "tests.fixtures.examples.queue"

_GOOD = f"""```python
from {_SUT} import Queue
def test_queue():
    queue = Queue(3)
    queue.enqueue(1)
```"""

_UNPARSEABLE = "```python\ndef test_broken(:\n    pass\n```"

_ALL_DROPPED = "```python\ndef test_dropped():\n    x = undefined_name(1)\n```"


class _FakeSecret:
    def get_secret_value(self) -> str:
        return "test-key"


class _UserPrompt(Prompt):
    _resource_name = "conversation_repair"

    def __init__(self, text: str) -> None:
        self.text = text
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["error_message"]

    def render_request(self) -> RenderedRequest:
        return RenderedRequest(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": self.text},
            ],
            model="test-model",
            temperature=0.0,
        )


def _value(variable: RuntimeVariable):
    output_variable = stat.statistics_tracker.output_variables.get(variable.name)
    return None if output_variable is None else output_variable.value


def _records(trace_dir) -> list[dict]:
    path = trace_dir / TRACE_FILE_NAME
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _response(content: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


@pytest.fixture
def trace_dir(tmp_path, monkeypatch):
    directory = tmp_path / "trace"
    monkeypatch.setattr(config.configuration.large_language_model, "trace_dir", str(directory))
    monkeypatch.setattr(config.configuration.statistics_output, "report_dir", str(tmp_path))
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "test-model")
    reset_statement_ratio()
    return directory


@pytest.fixture
def agent(monkeypatch, trace_dir):  # noqa: ARG001
    """A real agent whose OpenAI SDK client is mocked."""
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    monkeypatch.setattr("pynguin.large_language_model.client.require_api_key", _FakeSecret)
    sdk = MagicMock()
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", lambda **_: sdk)
    llm_agent = LLMAgent()
    llm_agent.sdk = sdk  # type: ignore[attr-defined]
    return llm_agent


@pytest.fixture
def context(monkeypatch):
    from pynguin.analyses.module import generate_test_cluster  # noqa: PLC0415

    monkeypatch.setattr(config.configuration, "module_name", _SUT)
    return ChromosomeContext(
        test_cluster=generate_test_cluster(_SUT),
        test_factory=MagicMock(),
        fitness_functions=[],
        coverage_functions=[],
    )


def test_write_record_is_a_no_op_without_trace_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "trace_dir", "")
    monkeypatch.chdir(tmp_path)

    write_record(LLMCallRecord(purpose="initial", prompt=[]))

    assert not list(tmp_path.iterdir())


def test_write_record_appends_one_json_line_per_record(trace_dir):
    write_record(LLMCallRecord(purpose="initial", prompt=[], outcome=CallOutcome.OK))
    write_record(LLMCallRecord(purpose="stall", prompt=[], targets=["Queue.enqueue"]))

    records = _records(trace_dir)
    assert [record["purpose"] for record in records] == ["initial", "stall"]
    assert records[0]["outcome"] == "ok"
    assert records[1]["targets"] == ["Queue.enqueue"]
    assert records[0]["call_id"] != records[1]["call_id"]


def test_write_record_logs_os_errors(tmp_path, monkeypatch, caplog):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(config.configuration.large_language_model, "trace_dir", str(blocker))

    write_record(LLMCallRecord(purpose="initial", prompt=[]))

    assert "Could not write LLM call trace" in caplog.text


def test_track_outcome_counts_everything_but_cache_hits():
    for outcome in (*CallOutcome, CallOutcome.OK):
        track_outcome(outcome)

    assert _value(RuntimeVariable.LLMCallsSucceeded) == 2
    assert _value(RuntimeVariable.LLMCallsFailed) == 1
    assert _value(RuntimeVariable.LLMCallsTimedOut) == 1


def test_query_writes_successful_call_with_usage(agent, trace_dir):
    agent.sdk.chat.completions.create.return_value = _response(_GOOD, 12, 7)

    assert agent.query(_UserPrompt("hello"), purpose="initial", targets=["Queue"]) == _GOOD

    (record,) = _records(trace_dir)
    assert record["purpose"] == "initial"
    assert record["targets"] == ["Queue"]
    assert record["prompt"][-1] == {"role": "user", "content": "hello"}
    assert record["response"] == _GOOD
    assert record["outcome"] == "ok"
    assert (record["input_tokens"], record["output_tokens"], record["retries"]) == (12, 7, 0)
    assert record["latency_seconds"] >= 0
    assert record["deserialization"] is None
    assert _value(RuntimeVariable.LLMCallsSucceeded) == 1


def test_query_defaults_purpose_to_prompt_name(agent, trace_dir):
    agent.sdk.chat.completions.create.return_value = _response(_GOOD)

    agent.query(_UserPrompt("hello"))

    assert _records(trace_dir)[0]["purpose"] == "conversation_repair"


def test_query_records_retries_and_timeout(agent, trace_dir, monkeypatch):
    import openai  # noqa: PLC0415

    monkeypatch.setattr(config.configuration.large_language_model, "max_retries", 2)
    monkeypatch.setattr("pynguin.large_language_model.client.time.sleep", lambda _: None)
    agent.sdk.chat.completions.create.side_effect = openai.APITimeoutError(request=MagicMock())

    assert agent.query(_UserPrompt("hello")) is None

    (record,) = _records(trace_dir)
    assert record["outcome"] == "timeout"
    assert record["retries"] == 1
    assert "Timeout" in record["error"]
    assert _value(RuntimeVariable.LLMCallsTimedOut) == 1


def test_query_records_failure(agent, trace_dir):
    agent.sdk.chat.completions.create.side_effect = ValueError("boom")

    assert agent.query(_UserPrompt("hello")) is None

    (record,) = _records(trace_dir)
    assert record["outcome"] == "failed"
    assert "boom" in record["error"]
    assert _value(RuntimeVariable.LLMCallsFailed) == 1


def test_query_records_cache_hit(agent, trace_dir, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    agent.cache = MagicMock()
    agent.cache.get.return_value = "cached"

    assert agent.query(_UserPrompt("hello")) == "cached"

    (record,) = _records(trace_dir)
    assert record["outcome"] == "cache_hit"
    assert _value(RuntimeVariable.LLMCallsSucceeded) is None


def test_query_async_writes_record(agent, trace_dir):
    agent._client.send_async = AsyncMock(return_value="async answer")

    assert asyncio.run(agent.query_async(_UserPrompt("hi"), purpose="stall")) == "async answer"

    (record,) = _records(trace_dir)
    assert (record["purpose"], record["outcome"]) == ("stall", "ok")


def test_query_async_records_cache_hit_and_failure(agent, trace_dir, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    agent.cache = MagicMock()
    agent.cache.get.side_effect = ["cached", None]
    agent._client.send_async = AsyncMock(side_effect=TimeoutError("slow"))

    assert asyncio.run(agent.query_async(_UserPrompt("a"))) == "cached"
    assert asyncio.run(agent.query_async(_UserPrompt("b"))) is None

    assert [record["outcome"] for record in _records(trace_dir)] == ["cache_hit", "timeout"]


def test_query_batch_writes_one_record_per_prompt(agent, trace_dir, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    agent.cache = MagicMock()
    agent.cache.get.side_effect = ["cached", None, None]

    async def fake_send(request, timeout=None, usage=None):  # noqa: ARG001
        await asyncio.sleep(0)
        if request.messages[-1]["content"] == "c":
            raise TimeoutError("slow")
        usage.input_tokens = 3
        return "fresh"

    agent._client.send_async = fake_send

    responses = agent.query_batch([_UserPrompt("a"), _UserPrompt("b"), _UserPrompt("c")])

    assert responses == ["cached", "fresh", None]
    records = _records(trace_dir)
    assert sorted(record["outcome"] for record in records) == ["cache_hit", "ok", "timeout"]
    assert {record["input_tokens"] for record in records if record["outcome"] == "ok"} == {3}


def test_query_batch_marks_all_failed_when_the_batch_raises(agent, trace_dir):
    agent._client.send_batch_async = AsyncMock(side_effect=ValueError("down"))

    assert agent.query_batch([_UserPrompt("a"), _UserPrompt("b")]) == [None, None]

    assert [record["outcome"] for record in _records(trace_dir)] == ["failed", "failed"]


def test_client_send_fills_usage(monkeypatch):
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    sdk = MagicMock()
    sdk.chat.completions.create.return_value = _response("x", 4, 2)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", lambda **_: sdk)
    client = OpenAIClient(api_key=_FakeSecret(), model="test-model")
    usage = CallUsage()

    client.send(_UserPrompt("a").render_request(), usage=usage)

    assert (usage.input_tokens, usage.output_tokens, usage.error) == (4, 2, None)
    assert client.is_timeout_error(TimeoutError())
    assert not client.is_timeout_error(ValueError())


def test_conversation_repair_prompt_extends_conversation():
    first = _UserPrompt("write tests")
    repair = ConversationRepairPrompt(first, "answer 1", "it broke")
    second = ConversationRepairPrompt(repair, "answer 2", "still broken")

    request = second.render_request()

    assert [message["role"] for message in request.messages] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    assert request.messages[2]["content"] == "answer 1"
    assert "it broke" in request.messages[3]["content"]
    assert "still broken" in request.messages[5]["content"]
    assert request.model == "test-model"


def test_generate_chromosomes_traces_deserialisation(agent, trace_dir, context):
    agent.sdk.chat.completions.create.return_value = _response(_GOOD)

    generation = agent.llm_test_case_handler.generate_chromosomes(
        _UserPrompt("write tests"), context, purpose="initial", targets=["Queue"]
    )

    assert len(generation.chromosomes) == 1
    assert generation.repairs_used == 0
    (record,) = _records(trace_dir)
    assert record["call_id"] == generation.call_id
    assert record["deserialization"]["status"] == "ok"
    assert record["deserialization"]["test_cases"] == 1
    assert record["deserialization"]["counts"]["admitted"] >= 1
    assert _value(RuntimeVariable.LLMParsedStatementRatio) == 1.0


def test_generate_chromosomes_without_repair_attempts_does_not_repair(agent, trace_dir, context):
    agent.sdk.chat.completions.create.return_value = _response(_UNPARSEABLE)

    generation = agent.llm_test_case_handler.generate_chromosomes(
        _UserPrompt("write tests"), context, purpose="initial"
    )

    assert generation.chromosomes == []
    assert agent.sdk.chat.completions.create.call_count == 1
    assert _records(trace_dir)[0]["deserialization"]["test_cases"] == 0


def test_broken_response_gets_at_most_repair_attempts_repairs(
    agent, trace_dir, context, monkeypatch
):
    monkeypatch.setattr(config.configuration.large_language_model, "repair_attempts", 2)
    agent.sdk.chat.completions.create.return_value = _response(_UNPARSEABLE)

    generation = agent.llm_test_case_handler.generate_chromosomes(
        _UserPrompt("write tests"), context, purpose="stall", targets=["Queue.enqueue"]
    )

    assert generation.chromosomes == []
    assert generation.repairs_used == 2
    records = _records(trace_dir)
    assert [record["purpose"] for record in records] == ["stall", "repair", "repair"]
    assert [record["repair_attempt"] for record in records] == [0, 1, 2]
    assert [record["parent_call_id"] for record in records] == [
        None,
        records[0]["call_id"],
        records[1]["call_id"],
    ]
    assert all(record["targets"] == ["Queue.enqueue"] for record in records)
    assert _value(RuntimeVariable.LLMRepairCalls) == 2
    # The repair is asked for in the same conversation, with the syntax error.
    last_messages = agent.sdk.chat.completions.create.call_args.kwargs["messages"]
    assert [message["role"] for message in last_messages][-4:] == [
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    assert "not valid Python" in last_messages[-1]["content"]


def test_repair_stops_once_a_response_is_usable(agent, trace_dir, context, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "repair_attempts", 3)
    agent.sdk.chat.completions.create.side_effect = [
        _response(_ALL_DROPPED),
        _response(_GOOD),
    ]

    generation = agent.llm_test_case_handler.generate_chromosomes(
        _UserPrompt("write tests"), context, purpose="initial"
    )

    assert len(generation.chromosomes) == 1
    assert generation.repairs_used == 1
    records = _records(trace_dir)
    assert len(records) == 2
    assert records[0]["deserialization"]["counts"] == {"dropped_unknown_names": 1}
    assert "None of the statements" in records[1]["prompt"][-1]["content"]
    assert _value(RuntimeVariable.LLMParsedStatementRatio) == pytest.approx(2 / 3)


def test_repair_respects_may_repair(agent, trace_dir, context, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "repair_attempts", 2)
    agent.sdk.chat.completions.create.return_value = _response("no code at all")

    generation = agent.llm_test_case_handler.generate_chromosomes(
        _UserPrompt("write tests"), context, purpose="initial", may_repair=lambda: False
    )

    assert generation.repairs_used == 0
    assert len(_records(trace_dir)) == 1


def test_failed_call_is_not_repaired(agent, trace_dir, context, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "repair_attempts", 2)
    agent.sdk.chat.completions.create.side_effect = ValueError("down")

    generation = agent.llm_test_case_handler.generate_chromosomes(
        _UserPrompt("write tests"), context, purpose="initial"
    )

    assert generation.response is None
    (record,) = _records(trace_dir)
    assert record["outcome"] == "failed"
    assert record["deserialization"] == {"status": None, "test_cases": 0, "counts": {}}


def test_repair_chromosomes_continues_the_conversation(agent, trace_dir, context, monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "repair_attempts", 1)
    agent.sdk.chat.completions.create.return_value = _response(_GOOD)
    handler = agent.llm_test_case_handler
    generation = handler.generate_chromosomes(_UserPrompt("write tests"), context, "initial")

    repaired = handler.repair_chromosomes(generation, "test_0 raised ValueError", context)

    assert repaired is not None
    assert repaired.repairs_used == 1
    assert handler.repair_chromosomes(repaired, "again", context) is None
    records = _records(trace_dir)
    assert records[1]["parent_call_id"] == records[0]["call_id"]
    assert "test_0 raised ValueError" in records[1]["prompt"][-1]["content"]


def test_repair_chromosomes_needs_a_response():
    handler = LLMTestCaseHandler(MagicMock())

    assert handler.repair_chromosomes(LLMGeneration(chromosomes=[]), "error", MagicMock()) is None


@pytest.mark.parametrize(
    ("code", "status", "counts", "has_tests", "expected"),
    [
        ("def f(:\n", "unparseable", {}, False, "not valid Python"),
        ("x = 1\n", "unparseable", {}, False, "could not be parsed"),
        ("x = 1\n", "ok", {}, False, "no `test_*` functions"),
        ("x = 1\n", "ok", {"dropped_unsupported_shape": 2}, True, "2 had an unsupported form"),
        ("x = 1\n", "ok", {"admitted": 1}, True, None),
    ],
)
def test_unusable_reason(code, status, counts, has_tests, expected):
    from collections import Counter  # noqa: PLC0415

    from pynguin.large_language_model.llmtestcasehandler import (  # noqa: PLC0415
        _unusable_reason,  # noqa: PLC2701
    )
    from pynguin.large_language_model.parsing.deserializer import (  # noqa: PLC0415
        DeserializationResult,
        Disposition,
        ParseStatus,
    )

    result = DeserializationResult(
        test_cases=[MagicMock()] if has_tests else [],
        status=ParseStatus(status),
        counts=Counter({Disposition(name): value for name, value in counts.items()}),
    )

    reason = _unusable_reason(code, result)

    if expected is None:
        assert reason is None
    else:
        assert expected in reason
