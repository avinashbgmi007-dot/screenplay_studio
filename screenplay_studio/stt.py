"""Local speech-to-text for hands-free dictation.

Privacy contract (same as llama-server): everything stays on this machine.
Two engines, both local:

1. **Built-in** -- `faster-whisper` runs inside this process. The tiny
   multilingual model is downloaded ONCE to a local cache on first use and
   then works offline forever. Handles en/hi/te.
2. **External-local (optional)** -- if you already run a `whisper.cpp`
   server beside your llama-server, set SCREENPLAY_STUDIO_WHISPER_URL to
   `http://localhost:<port>` and audio is POSTed there instead.

No cloud APIs, no API keys, ever. The heavy import is lazy so the rest of
the desk never pays for it (and pytest never downloads anything).
"""
import os
import tempfile

import requests

# "auto" lets whisper detect the spoken language per utterance
_LANG_CODES = {"auto": None, "en": "en", "hi": "hi", "te": "te"}

EXTERNAL_WHISPER_URL = os.environ.get("SCREENPLAY_STUDIO_WHISPER_URL", "").strip()
MODEL_SIZE = os.environ.get("SCREENPLAY_STUDIO_STT_MODEL", "tiny")

_model_cache = {}


class STTUnavailableError(RuntimeError):
    """Raised when no local STT engine is usable, with an actionable message."""


def supported_languages():
    return list(_LANG_CODES.keys())


def _get_model():
    """Lazy-load + cache the faster-whisper model (one download, then offline)."""
    global _model_cache
    if MODEL_SIZE in _model_cache:
        return _model_cache[MODEL_SIZE]
    try:
        from faster_whisper import WhisperModel  # lazy: only dictation pays
    except ImportError as e:
        raise STTUnavailableError(
            "Local transcription needs the faster-whisper package "
            '(pip install "faster-whisper>=1.0.0"). '
            "It is not installed in this environment."
        ) from e
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    _model_cache[MODEL_SIZE] = model
    return model


def transcribe(audio_bytes: bytes, filename: str = "audio.webm", language: str = "auto") -> dict:
    """Transcribe raw recorded audio bytes -> {'text', 'language', 'engine'}."""
    lang = (language or "auto").lower()
    if lang not in _LANG_CODES:
        raise ValueError(f"Unsupported speech language '{language}'. Supported: {', '.join(_LANG_CODES)}.")
    if not audio_bytes:
        raise ValueError("No audio data received.")

    if EXTERNAL_WHISPER_URL:
        return _transcribe_external(audio_bytes, filename, lang)

    suffix = os.path.splitext(filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    try:
        model = _get_model()
        segments, info = model.transcribe(path, language=_LANG_CODES[lang], beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
        if not text and lang != "auto":
            # Forcing a language can mis-decode audio that isn't really in it
            # into an EMPTY transcript (e.g. English speech forced through
            # 'hi'). One auto-detect retry rescues the utterance instead of
            # handing the writer nothing.
            segments, info = model.transcribe(path, language=None, beam_size=1)
            text = " ".join(s.text.strip() for s in segments).strip()
        return {
            "text": text,
            "language": getattr(info, "language", None) or lang,
            "engine": f"faster-whisper:{MODEL_SIZE}",
        }
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _transcribe_external(audio_bytes: bytes, filename: str, lang: str) -> dict:
    """POST multipart audio to a user-run whisper.cpp server (still localhost)."""
    url = EXTERNAL_WHISPER_URL.rstrip("/")
    if not url.startswith(("http://localhost", "http://127.0.0.1")):
        raise STTUnavailableError(
            "SCREENPLAY_STUDIO_WHISPER_URL must point at a LOCAL whisper server "
            "(localhost/127.0.0.1) -- this desk never sends audio off the machine."
        )
    try:
        resp = requests.post(f"{url}/inference", files={"file": (filename or "audio.webm", audio_bytes)},
                             data={"response_format": "json"}, timeout=120)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise STTUnavailableError(
            f"The whisper server at {url} could not be reached ({e}). "
            "Start it, or unset SCREENPLAY_STUDIO_WHISPER_URL to use built-in transcription."
        ) from e
    data = {}
    try:
        data = resp.json()
    except ValueError:
        pass
    return {"text": (data.get("text") or "").strip(), "language": lang, "engine": "whisper-server"}
