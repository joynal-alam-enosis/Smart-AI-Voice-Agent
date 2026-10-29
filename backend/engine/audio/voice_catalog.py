"""Voice Catalog and Acoustic Metadata Registry.

Defines supported voices for local Kokoro-82M, Piper, and cloud providers (Cartesia, ElevenLabs),
along with their acoustic capabilities, gender, accent, and recommended role mappings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

MIN_SPEED = 0.70
MAX_SPEED = 1.40
MIN_PITCH = -20.0
MAX_PITCH = 20.0


@dataclass(frozen=True)
class VoiceProfile:
    """Acoustic profile and metadata for a voice."""

    voice_id: str
    name: str
    provider: Literal["kokoro", "piper", "cartesia", "elevenlabs"]
    gender: Literal["female", "male", "neutral"]
    accent: str
    recommended_speed: float = 1.00
    description: str = ""
    role_fit: tuple[str, ...] = field(default_factory=tuple)


# Registry of native Kokoro-82M voices
KOKORO_VOICES: dict[str, VoiceProfile] = {
    "af_sarah": VoiceProfile(
        voice_id="af_sarah",
        name="Sarah",
        provider="kokoro",
        gender="female",
        accent="en-US",
        recommended_speed=1.00,
        description="Warm, luxurious, inviting tone. Perfect for Front Desk Concierge.",
        role_fit=("hotel_frontdesk", "receptionist", "customer_care"),
    ),
    "af_bella": VoiceProfile(
        voice_id="af_bella",
        name="Bella",
        provider="kokoro",
        gender="female",
        accent="en-US",
        recommended_speed=1.00,
        description="Dynamic, expressive and friendly American female voice.",
        role_fit=("dining_orders", "travel_desk"),
    ),
    "am_adam": VoiceProfile(
        voice_id="am_adam",
        name="Adam",
        provider="kokoro",
        gender="male",
        accent="en-US",
        recommended_speed=1.05,
        description="Crisp, confident, efficient American male voice.",
        role_fit=("room_service", "concierge", "drive_thru"),
    ),
    "am_michael": VoiceProfile(
        voice_id="am_michael",
        name="Michael",
        provider="kokoro",
        gender="male",
        accent="en-US",
        recommended_speed=1.00,
        description="Professional, authoritative and calm American male voice.",
        role_fit=("billing", "escalations", "receptionist"),
    ),
    "bf_emma": VoiceProfile(
        voice_id="bf_emma",
        name="Emma",
        provider="kokoro",
        gender="female",
        accent="en-GB",
        recommended_speed=0.98,
        description="Polished, refined British female voice. Ideal for luxury 5-star concierge.",
        role_fit=("luxury_concierge", "vip_desk"),
    ),
    "bm_george": VoiceProfile(
        voice_id="bm_george",
        name="George",
        provider="kokoro",
        gender="male",
        accent="en-GB",
        recommended_speed=0.95,
        description="Distinguished, reassuring British male voice with deep timbre.",
        role_fit=("security", "escalations", "general_manager"),
    ),
    "ef_dora": VoiceProfile(
        voice_id="ef_dora",
        name="Dora",
        provider="kokoro",
        gender="female",
        accent="es-ES",
        recommended_speed=1.00,
        description="Multilingual native Spanish/English female voice.",
        role_fit=("multilingual_support", "travel_desk"),
    ),
}

# Cloud Voice Registry
CLOUD_VOICES: dict[str, VoiceProfile] = {
    # Cartesia Sonic
    "86e30c1d-714b-4074-a1f2-1cb6b552fb49": VoiceProfile(
        voice_id="86e30c1d-714b-4074-a1f2-1cb6b552fb49",
        name="Cartesia Sarah (Warm)",
        provider="cartesia",
        gender="female",
        accent="en-US",
        recommended_speed=1.00,
        description="Ultra-low latency Cartesia Sonic warm conversational voice.",
        role_fit=("hotel_frontdesk", "receptionist"),
    ),
    "248be419-c632-4f23-adf1-5324ed7dbf10": VoiceProfile(
        voice_id="248be419-c632-4f23-adf1-5324ed7dbf10",
        name="Cartesia Colin (British)",
        provider="cartesia",
        gender="male",
        accent="en-GB",
        recommended_speed=1.00,
        description="Polite British male voice for concierge operations.",
        role_fit=("concierge", "vip_desk"),
    ),
    # ElevenLabs
    "21m00Tcm4TlvDq8ikWAM": VoiceProfile(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        name="Rachel",
        provider="elevenlabs",
        gender="female",
        accent="en-US",
        recommended_speed=1.00,
        description="ElevenLabs signature calm and engaging voice.",
        role_fit=("hotel_frontdesk", "customer_care"),
    ),
    # Piper local
    "en_US-lessac-medium": VoiceProfile(
        voice_id="en_US-lessac-medium",
        name="Lessac",
        provider="piper",
        gender="female",
        accent="en-US",
        recommended_speed=1.00,
        description="Piper lightweight local TTS model.",
        role_fit=("fallback",),
    ),
}

# Unified Voice Registry
ALL_VOICES: dict[str, VoiceProfile] = {**KOKORO_VOICES, **CLOUD_VOICES}


def get_voice_profile(voice_id: str, provider: str = "kokoro") -> VoiceProfile:
    """Retrieves the voice profile for a given voice_id, falling back gracefully."""
    if voice_id in ALL_VOICES:
        return ALL_VOICES[voice_id]

    # Provider-specific fallback
    if provider == "kokoro":
        return KOKORO_VOICES["af_sarah"]
    elif provider == "cartesia":
        return CLOUD_VOICES["86e30c1d-714b-4074-a1f2-1cb6b552fb49"]
    elif provider == "elevenlabs":
        return CLOUD_VOICES["21m00Tcm4TlvDq8ikWAM"]
    elif provider == "piper":
        return CLOUD_VOICES["en_US-lessac-medium"]

    # Global fallback
    return KOKORO_VOICES["af_sarah"]


def list_available_voices(
    provider: str | None = None,
    gender: str | None = None,
) -> list[VoiceProfile]:
    """Returns a list of voices filtered by provider and/or gender."""
    voices = list(ALL_VOICES.values())

    if provider:
        voices = [v for v in voices if v.provider == provider]

    if gender:
        voices = [v for v in voices if v.gender == gender]

    return voices


def get_default_voice_for_role(
    role: str,
    provider: str = "kokoro",
    gender: str = "female",
) -> VoiceProfile:
    """Finds the most appropriate voice for a given role, provider, and gender."""
    candidates = list_available_voices(provider=provider, gender=gender)
    for voice in candidates:
        if role in voice.role_fit:
            return voice

    if candidates:
        return candidates[0]

    return get_voice_profile("af_sarah", provider="kokoro")
