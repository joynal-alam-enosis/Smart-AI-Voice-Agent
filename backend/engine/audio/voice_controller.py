"""Dynamic In-Call Voice and Acoustic Controller.

Manages runtime acoustic adjustments (speed, pitch, voice_id) and parses
caller conversational pacing requests (e.g. 'speak slower', 'switch to male voice')
to push seamless TTS update frames with zero audio interruption.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from backend.engine.audio.voice_catalog import (
    MAX_PITCH,
    MAX_SPEED,
    MIN_PITCH,
    MIN_SPEED,
    VoiceProfile,
    get_voice_profile,
    list_available_voices,
)

logger = logging.getLogger(__name__)

# Verbal acoustic command regex patterns
RE_SPEAK_SLOWER = re.compile(
    r"\b(speak\s+(?:a\s+(?:bit|little)\s+)?slower|talk\s+(?:a\s+(?:bit|little)\s+)?slower|slow\s+down|too\s+fast)\b",
    re.IGNORECASE,
)
RE_SPEAK_FASTER = re.compile(
    r"\b(speak\s+(?:a\s+(?:bit|little)\s+)?faster|talk\s+(?:a\s+(?:bit|little)\s+)?faster|speed\s+up|too\s+slow)\b",
    re.IGNORECASE,
)
RE_SWITCH_MALE = re.compile(
    r"\b(switch\s+to\s+(?:a\s+)?male\s+voice|talk\s+to\s+a\s+man|male\s+voice|change\s+to\s+(?:a\s+)?male)\b",
    re.IGNORECASE,
)
RE_SWITCH_FEMALE = re.compile(
    r"\b(switch\s+to\s+(?:a\s+)?female\s+voice|talk\s+to\s+a\s+woman|female\s+voice|change\s+to\s+(?:a\s+)?female)\b",
    re.IGNORECASE,
)


class VoiceController:
    """Controls session acoustic state and generates in-call TTS update frames."""

    def __init__(
        self,
        voice_id: str = "af_sarah",
        provider: str = "kokoro",
        speed: float = 1.00,
        pitch: float = 0.0,
    ) -> None:
        self.provider = provider
        self.profile = get_voice_profile(voice_id, provider=provider)
        self.voice_id = self.profile.voice_id
        self.speed = self._clamp_speed(speed)
        self.pitch = self._clamp_pitch(pitch)

    @staticmethod
    def _clamp_speed(speed: float) -> float:
        """Clamps speed between MIN_SPEED and MAX_SPEED, rounded to 2 decimal places."""
        return round(max(MIN_SPEED, min(MAX_SPEED, speed)), 2)

    @staticmethod
    def _clamp_pitch(pitch: float) -> float:
        """Clamps pitch between MIN_PITCH and MAX_PITCH, rounded to 1 decimal place."""
        return round(max(MIN_PITCH, min(MAX_PITCH, pitch)), 1)

    def adjust_speed(self, delta: float) -> float:
        """Adjusts current speaking speed by delta and returns the new clamped speed."""
        self.speed = self._clamp_speed(self.speed + delta)
        logger.info("Adjusted voice speed: delta=%.2f, new_speed=%.2f", delta, self.speed)
        return self.speed

    def adjust_pitch(self, delta: float) -> float:
        """Adjusts current vocal pitch by delta and returns the new clamped pitch."""
        self.pitch = self._clamp_pitch(self.pitch + delta)
        logger.info("Adjusted voice pitch: delta=%.1f, new_pitch=%.1f", delta, self.pitch)
        return self.pitch

    def switch_voice(self, new_voice_id: str) -> VoiceProfile:
        """Swaps the active voice profile."""
        new_profile = get_voice_profile(new_voice_id, provider=self.provider)
        self.profile = new_profile
        self.voice_id = new_profile.voice_id
        logger.info("Switched voice to: voice_id=%s (%s)", self.voice_id, self.profile.name)
        return self.profile

    def switch_gender(self, target_gender: str) -> VoiceProfile:
        """Finds and swaps to the best matching voice of the target gender."""
        candidates = list_available_voices(provider=self.provider, gender=target_gender)
        if candidates:
            # Pick first available or different from current
            new_voice = candidates[0]
            for c in candidates:
                if c.voice_id != self.voice_id:
                    new_voice = c
                    break
            return self.switch_voice(new_voice.voice_id)
        return self.profile

    def parse_voice_command(self, user_utterance: str) -> dict[str, Any] | None:
        """Inspects user speech for verbal pacing or voice adjustment commands.

        Returns:
            Dict describing action taken and verbal response, or None if no command matched.
        """
        if not user_utterance:
            return None

        text = user_utterance.strip()

        # 1. Pacing: Slower
        if RE_SPEAK_SLOWER.search(text):
            new_speed = self.adjust_speed(-0.15)
            return {
                "action": "adjust_speed",
                "delta": -0.15,
                "current_speed": new_speed,
                "spoken_ack": "I'll speak a bit slower for you.",
            }

        # 2. Pacing: Faster
        if RE_SPEAK_FASTER.search(text):
            new_speed = self.adjust_speed(+0.15)
            return {
                "action": "adjust_speed",
                "delta": +0.15,
                "current_speed": new_speed,
                "spoken_ack": "Certainly, picking up the pace.",
            }

        # 3. Voice: Switch to Male
        if RE_SWITCH_MALE.search(text):
            if self.profile.gender != "male":
                new_profile = self.switch_gender("male")
                return {
                    "action": "switch_voice",
                    "new_voice_id": new_profile.voice_id,
                    "spoken_ack": f"Certainly, switching to a male voice.",
                }
            return {
                "action": "none",
                "spoken_ack": "I am already speaking in a male voice. How can I help you?",
            }

        # 4. Voice: Switch to Female
        if RE_SWITCH_FEMALE.search(text):
            if self.profile.gender != "female":
                new_profile = self.switch_gender("female")
                return {
                    "action": "switch_voice",
                    "new_voice_id": new_profile.voice_id,
                    "spoken_ack": f"Certainly, switching to a female voice.",
                }
            return {
                "action": "none",
                "spoken_ack": "I am already speaking in a female voice. How can I assist you?",
            }

        return None

    def get_settings_delta(self) -> dict[str, Any]:
        """Returns the dictionary payload representing the active acoustic state."""
        return {
            "voice": self.voice_id,
            "speed": self.speed,
            "pitch": self.pitch,
        }

    def create_pipecat_update_frame(self) -> Any:
        """Constructs a Pipecat TTSUpdateSettingsFrame if pipecat is available.

        Falls back to a dictionary payload if Pipecat is not installed in the test environment.
        """
        try:
            from pipecat.frames.frames import TTSUpdateSettingsFrame
            from pipecat.services.settings import TTSSettings

            return TTSUpdateSettingsFrame(
                delta=TTSSettings(
                    voice=self.voice_id,
                )
            )
        except ImportError:
            return {
                "type": "TTSUpdateSettingsFrame",
                "voice": self.voice_id,
                "speed": self.speed,
                "pitch": self.pitch,
            }
