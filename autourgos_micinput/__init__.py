"""
autourgos-micinput
===================
Standalone, provider-agnostic microphone capture for the Autourgos
ecosystem. Zero dependency to import; `sounddevice` is required only to
actually open a `MicrophoneStream` (`pip install autourgos-micinput[mic]`).

Not tied to any specific LLM API -- yields raw PCM bytes from the system
microphone. Not depended on by autourgos-live (voice input to Gemini Live
is wired up by the caller, forwarding chunks to session.send_audio_chunk()
themselves -- see this package's README), nor by autourgos-openaichat /
autourgos-responses / autourgos-agent. Usable standalone by any caller that
wants microphone capture without any of those as a dependency.

Quick start::

    import asyncio
    from autourgos_micinput import MicrophoneStream

    async def main():
        async with MicrophoneStream(sample_rate=16000) as mic:
            async for chunk in mic:
                print(len(chunk), "bytes captured")

    asyncio.run(main())
"""

from .microphone import MicrophoneStream, load_sounddevice_module

from autourgos_core import package_version

__version__ = package_version("autourgos-micinput", fallback="0.1.2")

__all__ = [
    "MicrophoneStream",
    "load_sounddevice_module",
]
