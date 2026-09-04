# autourgos-micinput

[![Framework: Autourgos](https://img.shields.io/badge/Framework-Autourgos-orange.svg)](https://github.com/devxjitin)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://pypi.org/project/autourgos-micinput/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](https://github.com/devxjitin/autourgos-micinput/blob/main/LICENSE)
[![Author](https://img.shields.io/badge/Author-Jitin%20Kumar%20Sengar-blue.svg)](https://github.com/devxjitin)

Standalone, provider-agnostic **microphone capture** for the Autourgos framework. Extracted out of [autourgos-live](https://github.com/devxjitin/autourgos-live) so any package -- `autourgos-live`, `autourgos-openaichat`, `autourgos-responses`, `autourgos-agent`, or plain application code -- can capture raw PCM audio from the system microphone without depending on `autourgos-live` for it. This package knows nothing about any specific LLM API; it just yields bytes.

```python
import asyncio
from autourgos_micinput import MicrophoneStream

async def main():
    async with MicrophoneStream(sample_rate=16000) as mic:
        async for chunk in mic:
            print(len(chunk), "bytes captured, mime_type =", mic.mime_type)
            break  # just capture one chunk for this example

asyncio.run(main())
```

---

## Install

```bash
pip install "autourgos-micinput[mic]"
```

`sounddevice` is required to actually open a `MicrophoneStream` and is gated behind the `mic` extra -- `import autourgos_micinput` alone never requires it. Requires Python 3.10+.

---

## Usage

### With `autourgos-live` (voice input to Gemini Live)

`autourgos-live` does **not** depend on this package or re-export `MicrophoneStream` -- that was tried and reverted (see [autourgos-live's CHANGELOG](https://github.com/devxjitin/autourgos-live/blob/main/CHANGELOG.md), 0.3.0/0.4.0) because it made this package a mandatory install even for callers who never touch local audio (telephony, browser WebRTC, text-only). Install both separately and forward chunks yourself -- three lines:

```python
from autourgos_live import GeminiLiveSession
from autourgos_micinput import MicrophoneStream

async def pipe_microphone(session, **kwargs):
    async with MicrophoneStream(**kwargs) as mic:
        async for chunk in mic:
            await session.send_audio_chunk(chunk, mime_type=mic.mime_type)
```

### With `autourgos-openaichat` / `autourgos-responses` (voice input to a request/response call)

These packages don't integrate with `autourgos-micinput` directly -- capture audio yourself, run it through your own speech-to-text step, then pass the resulting text to `invoke()`/`create()`:

```python
import asyncio
from autourgos_micinput import MicrophoneStream

async def record_utterance(seconds: float = 3.0) -> bytes:
    chunks = []
    frames_needed = int(seconds * 1000 / 100)  # default chunk_ms=100
    async with MicrophoneStream(sample_rate=16000) as mic:
        async for chunk in mic:
            chunks.append(chunk)
            if len(chunks) >= frames_needed:
                break
    return b"".join(chunks)

# pcm = asyncio.run(record_utterance())
# text = my_own_speech_to_text(pcm)
# response = my_openaichat_model.invoke(text)
```

### With `autourgos-agent` (as a tool)

Wrap capture in an `@tool`-decorated function the same way any other tool is defined:

```python
from autourgos_agent import tool
from autourgos_micinput import MicrophoneStream
import asyncio

@tool
def record_audio(seconds: float = 3.0) -> bytes:
    """Record `seconds` of audio from the microphone and return raw 16kHz PCM bytes."""
    async def _record():
        chunks = []
        async with MicrophoneStream(sample_rate=16000) as mic:
            async for chunk in mic:
                chunks.append(chunk)
                if len(chunks) * 0.1 >= seconds:
                    break
        return b"".join(chunks)
    return asyncio.run(_record())
```

---

## API Reference

### `MicrophoneStream`

Async context manager; async-iterates raw 16-bit PCM chunks from the input device.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `sample_rate` | `int` | `16000` | PCM sample rate |
| `chunk_ms` | `int` | `100` | Capture chunk size in milliseconds |
| `channels` | `int` | `1` | Audio channel count |
| `device` | `int` | `None` | Input device index; `None` uses the system default |
| `max_queue_chunks` | `int` | `50` | Bounds the internal capture buffer (50 x 100ms = 5s default). Once full, the *oldest* buffered chunk is dropped for the newest one -- see `.dropped_chunk_count` |

| Attribute | Description |
|---|---|
| `.mime_type` | Pre-formatted `"audio/pcm;rate=<sample_rate>"`, ready to hand to a live-session `send_audio_chunk()`-style call |
| `.dropped_chunk_count` | How many buffered chunks have been dropped due to a full queue (slow consumer / stall) |

Raises `ImportError` (with an install hint) on `__aenter__` if the `mic` extra isn't installed -- never on `import autourgos_micinput`.

---

## License

Apache License 2.0, Copyright (c) 2026 Jitin Kumar Sengar
