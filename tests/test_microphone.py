"""
Tests for autourgos_micinput.MicrophoneStream against a fake 'sounddevice'
module - no real audio hardware / PortAudio involved.
"""

import asyncio
import sys
import types

import pytest

from autourgos_micinput import MicrophoneStream


class FakeRawStream:
    """Stand-in for sounddevice.RawInputStream."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False
        self.closed = False
        self._callback = kwargs.get("callback")

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        self.closed = True

    def emit(self, data):
        """Test helper: simulate the audio backend delivering a captured chunk."""
        self._callback(data, len(data), None, None)


@pytest.fixture
def fake_sounddevice(monkeypatch):
    fake_module = types.ModuleType("sounddevice")
    fake_module.RawInputStream = FakeRawStream
    monkeypatch.setitem(sys.modules, "sounddevice", fake_module)
    return fake_module


@pytest.fixture
def no_sounddevice(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)  # forces ImportError on `import sounddevice`


@pytest.mark.asyncio
async def test_microphone_stream_yields_captured_chunks(fake_sounddevice):
    async with MicrophoneStream(sample_rate=16000, chunk_ms=100) as mic:
        assert mic.mime_type == "audio/pcm;rate=16000"
        mic._stream.emit(b"\x01\x02")
        mic._stream.emit(b"\x03\x04")

        chunks = []
        async for chunk in mic:
            chunks.append(chunk)
            if len(chunks) == 2:
                break

    assert chunks == [b"\x01\x02", b"\x03\x04"]


@pytest.mark.asyncio
async def test_microphone_stream_starts_and_stops_underlying_stream(fake_sounddevice):
    async with MicrophoneStream() as mic:
        underlying = mic._stream
        assert underlying.started is True
    assert underlying.started is False
    assert underlying.closed is True


@pytest.mark.asyncio
async def test_microphone_stream_default_max_queue_chunks():
    mic = MicrophoneStream()
    assert mic.max_queue_chunks == 50  # 5s of buffered audio at the default 100ms chunk_ms
    assert mic.dropped_chunk_count == 0


@pytest.mark.asyncio
async def test_microphone_stream_drops_oldest_chunk_when_queue_full(fake_sounddevice):
    async with MicrophoneStream(sample_rate=16000, chunk_ms=100, max_queue_chunks=2) as mic:
        mic._stream.emit(b"chunk1")
        mic._stream.emit(b"chunk2")
        mic._stream.emit(b"chunk3")  # queue full at maxsize=2 -> drops chunk1, not chunk3
        for _ in range(3):
            await asyncio.sleep(0)  # let the call_soon_threadsafe-scheduled enqueues run

        chunks = []
        async for chunk in mic:
            chunks.append(chunk)
            if len(chunks) == 2:
                break

    assert chunks == [b"chunk2", b"chunk3"]
    assert mic.dropped_chunk_count == 1


@pytest.mark.asyncio
async def test_microphone_stream_no_drops_when_under_capacity(fake_sounddevice):
    async with MicrophoneStream(sample_rate=16000, chunk_ms=100, max_queue_chunks=10) as mic:
        mic._stream.emit(b"chunk1")
        mic._stream.emit(b"chunk2")
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    assert mic.dropped_chunk_count == 0


@pytest.mark.asyncio
async def test_microphone_stream_without_sounddevice_raises_import_error(no_sounddevice):
    with pytest.raises(ImportError, match="autourgos-micinput\\[mic\\]"):
        async with MicrophoneStream():
            pass


@pytest.mark.asyncio
async def test_microphone_stream_iterate_before_open_raises():
    mic = MicrophoneStream.__new__(MicrophoneStream)  # bypass __init__/connect
    mic._queue = None
    with pytest.raises(RuntimeError):
        async for _ in mic:
            pass
