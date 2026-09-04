"""
Microphone capture for autourgos-micinput.

Gated behind the `mic` extra (`pip install autourgos-micinput[mic]`, which
pulls in `sounddevice`) so importing this package never requires a
platform-specific audio dependency for callers who don't actually open a
MicrophoneStream. `sounddevice` is imported lazily inside the class, never
at module import time.

Provider-agnostic: this module knows nothing about any specific LLM API. It
yields raw PCM bytes from the system microphone; what a caller does with
those bytes (feed a live session, run local STT, hand off to a
request/response call) is out of scope here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Optional, Tuple

logger = logging.getLogger(__name__)


def load_sounddevice_module() -> Tuple[bool, Any, Optional[str]]:
    """Try to import the `sounddevice` package. Returns (available, module, error)."""
    try:
        import sounddevice as _sd
        return True, _sd, None
    except ImportError as exc:
        return False, None, str(exc)


class MicrophoneStream:
    """
    Async iterator yielding raw 16-bit PCM chunks captured from the default
    (or given) input device, at the given `sample_rate`.

    The internal buffer is bounded (`max_queue_chunks`, default 50 chunks --
    5 seconds at the default 100ms chunk_ms) so a network stall or a slow
    consumer doesn't let captured audio pile up in memory indefinitely with
    ever-growing latency. Once full, the *oldest* buffered chunk is dropped
    to make room for the newest one -- for live audio, freshness matters
    more than completeness; a caller that's fallen behind wants to catch up
    to "now", not eventually work through a growing backlog of stale audio.

    Usage::

        async with MicrophoneStream(sample_rate=16000) as mic:
            async for chunk in mic:
                handle_chunk(chunk, mime_type=mic.mime_type)
    """

    def __init__(
        self,
        *,
        sample_rate: int = 16000,
        chunk_ms: int = 100,
        channels: int = 1,
        device: Optional[int] = None,
        max_queue_chunks: int = 50,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.device = device
        self.mime_type = f"audio/pcm;rate={sample_rate}"
        self.max_queue_chunks = max_queue_chunks
        self._chunk_frames = sample_rate * chunk_ms // 1000
        self._available, self._sd, self._import_error = load_sounddevice_module()
        self._stream: Any = None
        self._queue: Optional["asyncio.Queue[bytes]"] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self.dropped_chunk_count = 0

    def _require_available(self) -> None:
        if not self._available:
            raise ImportError(
                "The 'sounddevice' package is required for microphone capture "
                f"(pip install autourgos-micinput[mic]). Import error: {self._import_error}"
            )

    async def __aenter__(self) -> "MicrophoneStream":
        self._require_available()
        self._loop = asyncio.get_running_loop()
        self._queue = asyncio.Queue(maxsize=self.max_queue_chunks)
        queue = self._queue
        loop = self._loop

        def _enqueue_dropping_oldest(chunk: bytes) -> None:
            # Runs on the event loop thread (scheduled via call_soon_threadsafe
            # below), not the audio callback thread -- safe to touch the queue.
            try:
                queue.put_nowait(chunk)
                return
            except asyncio.QueueFull:
                pass
            try:
                queue.get_nowait()  # drop the oldest buffered chunk
            except asyncio.QueueEmpty:
                pass
            self.dropped_chunk_count += 1
            logger.warning(
                "MicrophoneStream queue full (%d chunks); dropped the oldest buffered "
                "chunk to keep latency bounded (%d dropped so far).",
                self.max_queue_chunks, self.dropped_chunk_count,
            )
            try:
                queue.put_nowait(chunk)
            except asyncio.QueueFull:
                pass  # a concurrent consumer raced us and refilled it; drop this chunk too

        def _callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
            # Runs on sounddevice's own audio callback thread - never touch
            # the queue directly here, hop back onto the event loop instead.
            if status:
                logger.warning("Microphone input stream status: %s", status)
            loop.call_soon_threadsafe(_enqueue_dropping_oldest, bytes(indata))

        self._stream = self._sd.RawInputStream(
            samplerate=self.sample_rate,
            blocksize=self._chunk_frames,
            dtype="int16",
            channels=self.channels,
            device=self.device,
            callback=_callback,
        )
        self._stream.start()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def __aiter__(self) -> AsyncIterator[bytes]:
        return self._iterate()

    async def _iterate(self) -> AsyncIterator[bytes]:
        if self._queue is None:
            raise RuntimeError("MicrophoneStream is not open. Use 'async with MicrophoneStream(...) as mic:'.")
        while True:
            yield await self._queue.get()
