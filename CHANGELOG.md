# Changelog

## 0.1.1

- Internal: `load_sounddevice_module()`'s import-probing logic moved to `autourgos_core.try_import()` (new `autourgos-core>=0.1.0` dependency), and `_require_available()`'s conditional-raise moved to `autourgos_core.require_available()`. No behavior change -- `load_sounddevice_module()` stays available as a backward-compatible wrapper.

## 0.1.0

- Initial release: `MicrophoneStream` extracted verbatim out of `autourgos-live`'s `audio_io.py` into its own standalone, provider-agnostic package -- so `autourgos-live`, `autourgos-openaichat`, `autourgos-responses`, and `autourgos-agent` can all use microphone capture without any of them requiring it as a hard dependency of the others. `autourgos-live` does not depend on this package; a caller installs both and wires them together themselves (see this package's README). `SpeakerPlayer` stays in `autourgos-live` (genuinely Live-specific: plays back `AudioDelta` chunks).
- 7 tests ported from `autourgos-live`'s `test_audio_io.py`, no real audio hardware / PortAudio involved.
