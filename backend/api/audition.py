"""Local voice-audition adapter used by the administrative Voice Studio."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from backend.api.schemas import VoiceAuditionRequest
from backend.config.settings import AppSettings
from backend.engine.audio.voice_catalog import get_voice_profile


class VoiceAuditionUnavailable(RuntimeError):
    """Raised when the selected voice cannot be synthesized locally."""


def synthesize_audition(request: VoiceAuditionRequest, settings: AppSettings) -> bytes:
    """Generate a WAV preview through the installed local Kokoro runtime.

    Cloud voices are intentionally not proxied from the browser. Their provider keys
    remain server-side and the endpoint reports an actionable unavailable state until
    a server-side cloud audition adapter is configured.
    """
    profile = get_voice_profile(request.voice_id)
    if profile.voice_id != request.voice_id:
        raise VoiceAuditionUnavailable("The selected voice is no longer available in the catalog.")
    if profile.provider != "kokoro":
        raise VoiceAuditionUnavailable(
            f"{profile.name} needs its {profile.provider} audition adapter configured on the server."
        )

    model_path = Path(settings.kokoro_model_path)
    voices_path = Path(settings.kokoro_voices_path)
    if not model_path.exists() or not voices_path.exists():
        raise VoiceAuditionUnavailable("Local Kokoro model files are not available for a live audition yet.")

    try:
        from kokoro_onnx import Kokoro
        import soundfile as sound_file
    except ImportError as exc:
        raise VoiceAuditionUnavailable(
            "Install the optional Kokoro ONNX runtime to enable live local voice auditions."
        ) from exc

    engine = Kokoro(str(model_path), str(voices_path))
    samples, sample_rate = engine.create(
        request.text,
        voice=profile.voice_id,
        speed=request.speed,
        lang="en-us",
    )
    buffer = BytesIO()
    sound_file.write(buffer, samples, sample_rate, format="WAV")
    return buffer.getvalue()

