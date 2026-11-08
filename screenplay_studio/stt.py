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

from .net_guard import is_loopback_url
from screenplay_analyzer.http_transport import request_no_redirects

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


# The external engine may only ever talk to THIS machine — the same rule the
# model server obeys, so the answer lives in net_guard rather than here. The
# original guard was a string prefix and was bypassable twice over:
# "http://127.0.0.1@evil.com" (userinfo — the authority ends at the @) and
# "http://localhost.evil.com" (suffix) both matched the prefix while resolving
# to a REMOTE host. net_guard parses the URL and compares the real hostname.
def _assert_local_whisper(url: str) -> None:
    """Refuse any whisper-server URL that does not resolve to this machine."""
    if not is_loopback_url(url):
        raise STTUnavailableError(
            "SCREENPLAY_STUDIO_WHISPER_URL must point at a LOCAL whisper server "
            "(localhost/127.0.0.1/::1) -- this desk never sends audio off the machine."
        )


def engine_status() -> dict:
    """What dictation WILL actually do, and why — one answer for every caller.

    Gap 125: `/api/stt/languages` used to label itself `whisper-server` purely
    because `EXTERNAL_WHISPER_URL` was set, without running the guard that
    `/api/stt` applies. So for a remote URL the capability endpoint advertised
    an engine the transcribe endpoint then refused with a 503 — the writer was
    told dictation was configured, recorded a paragraph, and only then learned
    it was not. The label now comes from the SAME check the route enforces, so
    the two endpoints cannot disagree.

    Runs the real guard on purpose (`_assert_local_whisper`), not a re-implemented
    loopback test: a second copy is exactly how these two drift apart again.
    `is_loopback_url` is what actually decides, so a hand-edited URL that only
    LOOKS local (e.g. `http://127.0.0.1@evil.com`) is reported misconfigured.
    """
    if not EXTERNAL_WHISPER_URL:
        return {"engine": "faster-whisper"}
    try:
        _assert_local_whisper(EXTERNAL_WHISPER_URL)
    except STTUnavailableError as e:
        # Name the engine that WOULD have been used, and say plainly that this
        # configuration is refused — rather than claiming a working whisper
        # server. The reason travels so the UI can explain before the mic opens.
        return {"engine": "faster-whisper", "misconfigured": "whisper-server",
                "reason": str(e)}
    return {"engine": "whisper-server"}


def _transcribe_external(audio_bytes: bytes, filename: str, lang: str) -> dict:
    """POST multipart audio to a user-run whisper.cpp server (still localhost)."""
    url = EXTERNAL_WHISPER_URL.rstrip("/")
    _assert_local_whisper(url)
    try:
        resp = request_no_redirects(
            "post", f"{url}/inference",
            files={"file": (filename or "audio.webm", audio_bytes)},
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
