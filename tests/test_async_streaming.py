"""
Tests for v0.9.1 async streaming execution.

Covers: StreamChunk type, LLM async streaming, Agent async execution,
Orchestrator async streaming, and interface consistency.
"""

import json
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from dataclasses import dataclass

from nano_agent.llm.messages import StreamChunk, ToolCall
from nano_agent.llm.base import BaseLLM, LLMUsage
from nano_agent.agent.types import (
    AsyncExecutionHandle,
    ExecutionEvent,
    ExecutionEventType,
    ExecutionResult,
    ThinkResult,
)

# === Helpers ===


def _mock_httpx_stream(lines):
    """Build a mock httpx module with AsyncClient that yields the given lines."""

    async def mock_aiter_lines():
        for line in lines:
            yield line

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_client_instance = AsyncMock()
    mock_client_instance.stream = MagicMock(return_value=mock_stream_ctx)

    mock_client_ctx = AsyncMock()
    mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_httpx_module = MagicMock()
    mock_httpx_module.AsyncClient = MagicMock(return_value=mock_client_ctx)
    return mock_httpx_module


# === StreamChunk Tests ===


class TestStreamChunk:
    """Test StreamChunk dataclass."""

    def test_default_values(self):
        chunk = StreamChunk()
        assert chunk.text == ""
        assert chunk.tool_call is None
        assert chunk.is_tool_call_complete is False
        assert chunk.usage is None

    def test_text_chunk(self):
        chunk = StreamChunk(text="Hello")
        assert chunk.text == "Hello"
        assert chunk.is_tool_call_complete is False

    def test_tool_call_chunk(self):
        tc = ToolCall(id="tc1", name="test_tool", arguments={"key": "value"})
        chunk = StreamChunk(tool_call=tc, is_tool_call_complete=True)
        assert chunk.tool_call.name == "test_tool"
        assert chunk.is_tool_call_complete is True

    def test_usage_chunk(self):
        usage = LLMUsage(prompt_tokens=10, completion_tokens=5)
        chunk = StreamChunk(usage=usage)
        assert chunk.usage.prompt_tokens == 10


# === AsyncExecutionHandle Tests ===


class TestAsyncExecutionHandle:
    """Test AsyncExecutionHandle."""

    @pytest.mark.asyncio
    async def test_collect_result(self):
        async def gen():
            yield ExecutionEvent(type=ExecutionEventType.RUN_START, data={})
            yield ExecutionEvent(
                type=ExecutionEventType.RUN_END,
                data={},
                result=ExecutionResult(
                    response="done",
                    success=True,
                    iterations=1,
                    tool_calls=[],
                    tokens_used=10,
                    session_id="s1",
                ),
            )

        handle = AsyncExecutionHandle(events=gen())
        result = await handle.collect_result()
        assert result is not None
        assert result.response == "done"

    @pytest.mark.asyncio
    async def test_cancel(self):
        handle = AsyncExecutionHandle(events=AsyncMock())
        assert handle.cancelled is False
        handle.cancel()
        assert handle.cancelled is True

    @pytest.mark.asyncio
    async def test_collect_result_no_run_end(self):
        async def gen():
            yield ExecutionEvent(type=ExecutionEventType.RUN_START, data={})

        handle = AsyncExecutionHandle(events=gen())
        result = await handle.collect_result()
        assert result is None


# === BaseLLM Async Interface Tests ===


class TestBaseLLMAsyncInterface:
    """Test that all BaseLLM subclasses implement _chat_stream_async_impl."""

    def test_ollama_has_async_impl(self):
        from nano_agent.llm.ollama import OllamaLLM

        assert hasattr(OllamaLLM, "_chat_stream_async_impl")

    def test_openai_compatible_has_async_impl(self):
        from nano_agent.llm.openai_compatible import OpenAICompatibleLLM

        assert hasattr(OpenAICompatibleLLM, "_chat_stream_async_impl")

    def test_anthropic_has_async_impl(self):
        from nano_agent.llm.anthropic import AnthropicLLM

        assert hasattr(AnthropicLLM, "_chat_stream_async_impl")


# === OllamaLLM Async Streaming Tests ===


class TestOllamaLLMAsyncStream:
    """Test OllamaLLM._chat_stream_async_impl with mocked httpx."""

    @pytest.mark.asyncio
    async def test_text_streaming(self):
        from nano_agent.llm.ollama import OllamaLLM

        llm = OllamaLLM(model="llama3", base_url="http://localhost:11434")

        mock_lines = [
            json.dumps({"message": {"content": "Hello"}}),
            json.dumps({"message": {"content": " world"}}),
            json.dumps({"done": True, "prompt_eval_count": 10, "eval_count": 5}),
        ]

        with patch("nano_agent.llm.ollama.httpx", _mock_httpx_stream(mock_lines)):
            chunks = []
            async for chunk in llm._chat_stream_async_impl(
                messages=[{"role": "user", "content": "hi"}]
            ):
                chunks.append(chunk)

        text_chunks = [c for c in chunks if c.text]
        assert len(text_chunks) == 2
        assert text_chunks[0].text == "Hello"
        assert text_chunks[1].text == " world"

        usage_chunks = [c for c in chunks if c.usage is not None]
        assert len(usage_chunks) == 1
        assert usage_chunks[0].usage.prompt_tokens == 10

    @pytest.mark.asyncio
    async def test_tool_call_streaming(self):
        from nano_agent.llm.ollama import OllamaLLM

        llm = OllamaLLM(model="llama3", base_url="http://localhost:11434")

        mock_lines = [
            json.dumps({"message": {"content": ""}}),
            json.dumps(
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "function": {
                                    "name": "test_tool",
                                    "arguments": {"key": "val"},
                                }
                            }
                        ],
                    },
                    "done": True,
                    "prompt_eval_count": 10,
                    "eval_count": 5,
                }
            ),
        ]

        with patch("nano_agent.llm.ollama.httpx", _mock_httpx_stream(mock_lines)):
            chunks = []
            async for chunk in llm._chat_stream_async_impl(
                messages=[{"role": "user", "content": "hi"}]
            ):
                chunks.append(chunk)

        tc_chunks = [c for c in chunks if c.is_tool_call_complete]
        assert len(tc_chunks) == 1
        assert tc_chunks[0].tool_call.name == "test_tool"


# === OpenAICompatibleLLM Async Streaming Tests ===


class TestOpenAICompatibleLLMAsyncStream:
    """Test OpenAICompatibleLLM._chat_stream_async_impl with mocked httpx."""

    @pytest.mark.asyncio
    async def test_text_streaming(self):
        from nano_agent.llm.openai_compatible import OpenAICompatibleLLM

        llm = OpenAICompatibleLLM(
            model="gpt-4o", api_key="test-key", base_url="https://api.openai.com/v1"
        )

        mock_lines = [
            'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            'data: {"choices":[{"delta":{"content":" there"}}]}',
            "data: [DONE]",
        ]

        with patch(
            "nano_agent.llm.openai_compatible.httpx", _mock_httpx_stream(mock_lines)
        ):
            chunks = []
            async for chunk in llm._chat_stream_async_impl(
                messages=[{"role": "user", "content": "hi"}]
            ):
                chunks.append(chunk)

        text_chunks = [c for c in chunks if c.text]
        assert len(text_chunks) == 2
        assert text_chunks[0].text == "Hi"
        assert text_chunks[1].text == " there"

    @pytest.mark.asyncio
    async def test_tool_call_incremental(self):
        from nano_agent.llm.openai_compatible import OpenAICompatibleLLM

        llm = OpenAICompatibleLLM(
            model="gpt-4o", api_key="test-key", base_url="https://api.openai.com/v1"
        )

        mock_lines = [
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"tc1","function":{"name":"test_tool","arguments":""}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"key\\""}}]}}]}',
            'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":": \\"val\\"}"}}]}}]}',
            "data: [DONE]",
        ]

        with patch(
            "nano_agent.llm.openai_compatible.httpx", _mock_httpx_stream(mock_lines)
        ):
            chunks = []
            async for chunk in llm._chat_stream_async_impl(
                messages=[{"role": "user", "content": "hi"}]
            ):
                chunks.append(chunk)

        tc_chunks = [c for c in chunks if c.is_tool_call_complete]
        assert len(tc_chunks) == 1
        assert tc_chunks[0].tool_call.name == "test_tool"
        assert tc_chunks[0].tool_call.arguments == {"key": "val"}


# === AnthropicLLM Async Streaming Tests ===


class TestAnthropicLLMAsyncStream:
    """Test AnthropicLLM._chat_stream_async_impl with mocked AsyncAnthropic."""

    @pytest.mark.asyncio
    async def test_text_streaming(self):
        from nano_agent.llm.anthropic import AnthropicLLM

        # Skip Anthropic tests if anthropic SDK is not installed
        anthropic_sdk = pytest.importorskip("anthropic")

        llm = AnthropicLLM(api_key="test-key")

        async def mock_stream_events():
            delta_mock1 = MagicMock()
            delta_mock1.type = "text_delta"
            delta_mock1.text = "Hello"
            event1 = MagicMock()
            event1.type = "content_block_delta"
            event1.delta = delta_mock1
            yield event1

            delta_mock2 = MagicMock()
            delta_mock2.type = "text_delta"
            delta_mock2.text = " world"
            event2 = MagicMock()
            event2.type = "content_block_delta"
            event2.delta = delta_mock2
            yield event2

        class MockStream:
            def __init__(self, gen):
                self._gen = gen

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                return self._gen()

        mock_async_client = MagicMock()
        mock_async_client.messages.stream.return_value = MockStream(mock_stream_events)

        llm._async_client = mock_async_client

        chunks = []
        async for chunk in llm._chat_stream_async_impl(
            messages=[{"role": "user", "content": "hi"}]
        ):
            chunks.append(chunk)

        text_chunks = [c for c in chunks if c.text]
        assert len(text_chunks) == 2
        assert text_chunks[0].text == "Hello"
        assert text_chunks[1].text == " world"

    @pytest.mark.asyncio
    async def test_tool_call_streaming(self):
        from nano_agent.llm.anthropic import AnthropicLLM

        anthropic_sdk = pytest.importorskip("anthropic")

        llm = AnthropicLLM(api_key="test-key")

        async def mock_stream_events():
            block_start = MagicMock()
            block_start.type = "content_block_start"
            block_start.content_block = MagicMock()
            block_start.content_block.type = "tool_use"
            block_start.content_block.id = "tc1"
            block_start.content_block.name = "test_tool"
            yield block_start

            delta_mock = MagicMock()
            delta_mock.type = "input_json_delta"
            delta_mock.partial_json = '{"key": "val"}'
            event_delta = MagicMock()
            event_delta.type = "content_block_delta"
            event_delta.delta = delta_mock
            yield event_delta

            event_stop = MagicMock()
            event_stop.type = "content_block_stop"
            yield event_stop

        class MockStream:
            def __init__(self, gen):
                self._gen = gen

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                return self._gen()

        mock_async_client = MagicMock()
        mock_async_client.messages.stream.return_value = MockStream(mock_stream_events)

        llm._async_client = mock_async_client

        chunks = []
        async for chunk in llm._chat_stream_async_impl(
            messages=[{"role": "user", "content": "hi"}]
        ):
            chunks.append(chunk)

        tc_chunks = [c for c in chunks if c.is_tool_call_complete]
        assert len(tc_chunks) == 1
        assert tc_chunks[0].tool_call.name == "test_tool"
        assert tc_chunks[0].tool_call.arguments == {"key": "val"}


# === Agent Async Streaming Tests ===


def _make_mock_llm():
    """Create a properly mocked LLM for agent tests."""
    mock_llm = MagicMock(spec=BaseLLM)
    mock_llm.model = "test-model"
    mock_llm.supports_explicit_caching = False
    # Make query_context_length return None (no API query)
    mock_llm.query_context_length = MagicMock(return_value=None)
    return mock_llm


class TestThinkStreamAsync:
    """Test ReActAgent._think_stream_async() with mocked LLM."""

    @pytest.mark.asyncio
    async def test_token_by_token_think_text(self):
        from nano_agent.agent.react import ReActAgent
        from nano_agent.memory.short_term import ShortTermMemory
        from nano_agent.tools import ToolRegistry

        mock_llm = _make_mock_llm()
        memory = ShortTermMemory(max_messages=50)
        memory.set_system_prompt("Test")
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=5,
        )

        # Mock chat_stream_async to yield token-by-token
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="Hello")
            yield StreamChunk(text=" world")
            yield StreamChunk(
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            )

        mock_llm.chat_stream_async = mock_stream

        events = []
        async for event in agent._think_stream_async():
            events.append(event)

        # Should have THINK_START, 2x THINK_TEXT, THINK_END
        think_text_events = [
            e for e in events if e.type == ExecutionEventType.THINK_TEXT
        ]
        assert len(think_text_events) == 2
        assert think_text_events[0].text_chunk == "Hello"
        assert think_text_events[1].text_chunk == " world"

        think_end_events = [e for e in events if e.type == ExecutionEventType.THINK_END]
        assert len(think_end_events) == 1
        assert think_end_events[0].think_result.response_text == "Hello world"
        assert think_end_events[0].think_result.is_final is True


class TestRunStreamAsyncSimpleAnswer:
    """Test run_stream_async with a simple final answer (no tool calls)."""

    @pytest.mark.asyncio
    async def test_simple_answer(self):
        from nano_agent.agent.react import ReActAgent
        from nano_agent.memory.short_term import ShortTermMemory
        from nano_agent.tools import ToolRegistry

        mock_llm = _make_mock_llm()
        memory = ShortTermMemory(max_messages=50)
        memory.set_system_prompt("Test")
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=5,
            verbose=False,
        )

        # Mock chat_stream_async — final answer, no tool calls
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="The answer is 42")
            yield StreamChunk(
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            )

        mock_llm.chat_stream_async = mock_stream

        handle = agent.run_stream_async("What is the answer?")
        result = await handle.collect_result()

        assert result is not None
        assert result.success is True
        assert "42" in result.response


class TestRunStreamAsyncCancellation:
    """Test run_stream_async cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_during_execution(self):
        from nano_agent.agent.react import ReActAgent
        from nano_agent.memory.short_term import ShortTermMemory
        from nano_agent.tools import ToolRegistry

        mock_llm = _make_mock_llm()
        memory = ShortTermMemory(max_messages=50)
        memory.set_system_prompt("Test")
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=5,
            verbose=False,
        )
        # Disable routing so the main loop is entered
        agent._routing_max_tools = -1
        agent.smart_optimization_config.routing_enabled = False
        agent.smart_optimization_config.prejudgment_enabled = False

        # Mock chat_stream_async — yield one chunk, then check cancellation
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="Thinking...")
            yield StreamChunk(
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            )

        mock_llm.chat_stream_async = mock_stream

        handle = agent.run_stream_async("Explain quantum computing in detail")
        # Cancel before consuming events
        handle.cancel()

        events = []
        async for event in handle.events:
            events.append(event)

        cancelled_events = [e for e in events if e.type == ExecutionEventType.CANCELLED]
        # The cancel should be detected at the start of the iteration loop
        assert len(cancelled_events) >= 1


# === Sync/Async Parity Test ===


class TestSyncAsyncParity:
    """Test that sync and async paths produce equivalent results."""

    @pytest.mark.asyncio
    async def test_same_final_result(self):
        from nano_agent.agent.react import ReActAgent
        from nano_agent.memory.short_term import ShortTermMemory
        from nano_agent.tools import ToolRegistry

        mock_llm = _make_mock_llm()
        memory = ShortTermMemory(max_messages=50)
        memory.set_system_prompt("Test")
        registry = ToolRegistry()

        agent = ReActAgent(
            llm=mock_llm,
            memory=memory,
            tool_registry=registry,
            max_iterations=5,
            verbose=False,
        )

        # Mock sync chat
        mock_llm.chat.return_value = (
            "The answer is 42",
            [],
            LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        # Mock async stream
        async def mock_stream(*args, **kwargs):
            yield StreamChunk(text="The answer is 42")
            yield StreamChunk(
                usage=LLMUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            )

        mock_llm.chat_stream_async = mock_stream

        # Sync run
        sync_result = agent.run("What is the answer?")

        # Reset memory for async run
        memory.clear()
        memory.set_system_prompt("Test")

        # Async run
        async_result = await agent.run_async("What is the answer?")

        assert sync_result.response == async_result.response
        assert sync_result.success == async_result.success


# === StreamingConfig Tests ===


class TestStreamingConfig:
    """Test StreamingConfig in schema."""

    def test_default_mode(self):
        from nano_agent.config.schema import StreamingConfig

        config = StreamingConfig()
        assert config.mode == "sync"

    def test_async_mode(self):
        from nano_agent.config.schema import StreamingConfig

        config = StreamingConfig(mode="async")
        assert config.mode == "async"

    def test_config_has_streaming(self):
        from nano_agent.config.schema import Config

        config = Config()
        assert hasattr(config, "streaming")
        assert config.streaming.mode == "sync"


class TestMessageNormalizer:
    """Tests for provider-specific message normalizers."""

    def test_openai_normalizer_noop(self):
        from nano_agent.llm.normalizer import OpenAINormalizer

        n = OpenAINormalizer()
        msgs = [{"role": "assistant", "tool_calls": []}]
        assert n.normalize_request_messages(msgs) is msgs

    def test_deepseek_normalizer_adds_reasoning_content(self):
        from nano_agent.llm.normalizer import DeepSeekNormalizer

        n = DeepSeekNormalizer()
        msgs = [{"role": "assistant", "tool_calls": [{}]}]
        n.normalize_request_messages(msgs)
        assert msgs[0].get("reasoning_content") == ""

    def test_deepseek_normalizer_skips_if_present(self):
        from nano_agent.llm.normalizer import DeepSeekNormalizer

        n = DeepSeekNormalizer()
        msgs = [
            {"role": "assistant", "tool_calls": [{}], "reasoning_content": "thinking"}
        ]
        n.normalize_request_messages(msgs)
        assert msgs[0]["reasoning_content"] == "thinking"

    def test_xfyun_normalizer_skips_empty_id(self):
        from nano_agent.llm.normalizer import XfyunNormalizer

        n = XfyunNormalizer()
        calls = {0: {"id": "call_1", "name": "get_stats", "arguments_parts": []}}
        n.normalize_stream_delta(
            {"tool_calls": [{"index": 0, "id": ""}]},
            calls,
        )
        assert calls[0]["id"] == "call_1"

    def test_select_normalizer_by_model(self):
        from nano_agent.llm.normalizer import (
            select_normalizer,
            DeepSeekNormalizer,
            XfyunNormalizer,
        )

        assert isinstance(select_normalizer("deepseek-v4-flash"), DeepSeekNormalizer)
        assert isinstance(select_normalizer("astron-code-latest"), XfyunNormalizer)
        assert isinstance(
            select_normalizer("gpt-4o"), type(select_normalizer("unknown"))
        )
