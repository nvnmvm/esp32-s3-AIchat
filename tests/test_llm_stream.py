import asyncio
import json

import httpx

from app.providers.llm.openai_stream import stream_openai_compatible_chat
from app import main


def test_stream_openai_compatible_chat_parses_sse_and_request_options():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        body = "".join(
            [
                ": keep-alive\n\n",
                'data: {"choices":[{"delta":{"reasoning_content":"内部推理"}}]}\n\n',
                'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n',
                'data: {"choices":[{"delta":{"content":"，世界。"}}]}\n\n',
                "data: [DONE]\n\n",
            ]
        )
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())

    async def collect():
        return [
            chunk
            async for chunk in stream_openai_compatible_chat(
                "测试问题",
                provider_name="DeepSeek",
                api_key="secret",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-flash",
                timeout_seconds=5,
                max_tokens=256,
                history=[{"role": "assistant", "content": "上一轮"}],
                disable_thinking=True,
                transport=httpx.MockTransport(handler),
            )
        ]

    assert asyncio.run(collect()) == ["你好", "，世界。"]
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["max_tokens"] == 256
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["payload"]["messages"][-2:] == [
        {"role": "assistant", "content": "上一轮"},
        {"role": "user", "content": "测试问题"},
    ]


def test_stream_openai_compatible_chat_rejects_empty_stream():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"data: [DONE]\n\n")

    async def collect():
        return [
            chunk
            async for chunk in stream_openai_compatible_chat(
                "测试问题",
                provider_name="test-provider",
                api_key="secret",
                base_url="https://example.com/v1",
                model="test-model",
                timeout_seconds=5,
                max_tokens=256,
                transport=httpx.MockTransport(handler),
            )
        ]

    try:
        asyncio.run(collect())
        raise AssertionError("empty SSE stream should fail")
    except RuntimeError as exc:
        assert "empty streaming answer" in str(exc)


def test_stream_answer_chunks_keeps_partial_output_without_appending_fallback(monkeypatch):
    async def broken_stream(*_args, **_kwargs):
        yield "已经生成。"
        raise httpx.ReadError("connection lost")

    monkeypatch.setattr(main, "stream_openai_compatible_chat", broken_stream)
    monkeypatch.setattr(main, "LLM_PROVIDER", "auto")
    monkeypatch.setattr(main, "LLM_STREAMING_ENABLED", True)
    monkeypatch.setattr(main, "DEEPSEEK_API_KEY", "secret")

    async def collect():
        return [chunk async for chunk in main.stream_answer_chunks("测试")]

    assert asyncio.run(collect()) == ["已经生成。"]
