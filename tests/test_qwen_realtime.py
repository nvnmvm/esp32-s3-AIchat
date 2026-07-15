import asyncio
import json

from app.providers.asr.qwen_realtime import QwenRealtimeASRSession


class FakeWebSocket:
    def __init__(self):
        self.sent = []
        self.closed = False
        self.messages = iter(
            [
                json.dumps(
                    {
                        "type": "conversation.item.input_audio_transcription.text",
                        "text": "今天天气",
                        "stash": "不错",
                    }
                ),
                json.dumps(
                    {
                        "type": "conversation.item.input_audio_transcription.completed",
                        "transcript": "今天天气不错",
                    }
                ),
                json.dumps({"type": "session.finished"}),
            ]
        )

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.messages)
        except StopIteration:
            raise StopAsyncIteration

    async def send(self, message):
        self.sent.append(json.loads(message))

    async def close(self):
        self.closed = True


def test_qwen_realtime_endpoint_uses_workspace_region_and_model():
    session = QwenRealtimeASRSession(
        api_key="sk-test",
        workspace_id="ws-test",
        region="cn-beijing",
        model="qwen3-asr-flash-realtime",
    )

    assert session.endpoint == (
        "wss://ws-test.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime"
        "?model=qwen3-asr-flash-realtime"
    )


def test_qwen_realtime_streams_pcm_and_collects_final(monkeypatch):
    fake = FakeWebSocket()

    async def fake_connect(*args, **kwargs):
        assert kwargs["additional_headers"]["Authorization"] == "Bearer sk-test"
        return fake

    async def run():
        import websockets.asyncio.client

        monkeypatch.setattr(websockets.asyncio.client, "connect", fake_connect)
        session = QwenRealtimeASRSession(
            api_key="sk-test",
            workspace_id="ws-test",
            finish_timeout_seconds=1,
        )
        await session.start()
        await session.append_audio(b"\x01\x02")
        transcript = await session.finish()
        events = [await session.events.get(), await session.events.get()]
        return transcript, events

    transcript, events = asyncio.run(run())

    assert transcript == "今天天气不错"
    assert events[0].type == "partial"
    assert events[0].text == "今天天气不错"
    assert events[1].type == "final"
    assert [message["type"] for message in fake.sent] == [
        "session.update",
        "input_audio_buffer.append",
        "session.finish",
    ]
    assert fake.closed is True
