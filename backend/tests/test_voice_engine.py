"""Unit tests for the Audio and Dynamic Voice Engine.

Tests:
1. Speech Text Normalizer (currencies, booking codes, room numbers, dates, abbreviations).
2. Voice Catalog & Metadata Registry (Kokoro voices, gender filtering, fallbacks).
3. Dynamic Voice Controller (speed/pitch clamping, verbal command parsing, in-call adaptation).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.engine.audio.normalizer import int_to_words, normalize_speech_text
from backend.engine.audio.voice_catalog import (
    MAX_PITCH,
    MAX_SPEED,
    MIN_PITCH,
    MIN_SPEED,
    get_default_voice_for_role,
    get_voice_profile,
    list_available_voices,
)
from backend.engine.audio.voice_controller import VoiceController


class TestTextNormalizer(unittest.TestCase):
    """Tests for text normalization and phonetic expansion."""

    def test_int_to_words(self):
        """Validates integer conversion to English words."""
        self.assertEqual(int_to_words(0), "zero")
        self.assertEqual(int_to_words(5), "five")
        self.assertEqual(int_to_words(-12), "negative twelve")
        self.assertEqual(int_to_words(18), "eighteen")
        self.assertEqual(int_to_words(42), "forty-two")
        self.assertEqual(int_to_words(180), "one hundred eighty")
        self.assertEqual(int_to_words(1005), "one thousand five")
        self.assertEqual(int_to_words(2540), "two thousand five hundred forty")
        self.assertEqual(int_to_words(1_250_000), "one million two hundred fifty thousand")

    def test_empty_and_non_string_inputs(self):
        """Validates graceful handling of empty or non-string inputs."""
        self.assertEqual(normalize_speech_text(""), "")
        self.assertEqual(normalize_speech_text(None), "")
        self.assertEqual(normalize_speech_text(180), "180")

    def test_currency_whole_dollars(self):
        """Validates whole dollar amounts."""
        self.assertEqual(normalize_speech_text("$1"), "one dollar")
        self.assertEqual(normalize_speech_text("$50"), "fifty dollars")
        self.assertEqual(normalize_speech_text("$180"), "one hundred eighty dollars")
        self.assertEqual(normalize_speech_text("$1,200"), "one thousand two hundred dollars")

    def test_currency_with_cents(self):
        """Validates dollars and cents combinations."""
        self.assertEqual(
            normalize_speech_text("$180.50"),
            "one hundred eighty dollars and fifty cents",
        )
        self.assertEqual(
            normalize_speech_text("$25.05"),
            "twenty-five dollars and five cents",
        )
        self.assertEqual(normalize_speech_text("$0.75"), "seventy-five cents")

    def test_currency_with_rates(self):
        """Validates rate suffixes like /night and /nt."""
        self.assertEqual(
            normalize_speech_text("$180/night"),
            "one hundred eighty dollars per night",
        )
        self.assertEqual(
            normalize_speech_text("$250/nt"),
            "two hundred fifty dollars per night",
        )
        self.assertEqual(
            normalize_speech_text("$40/hr"),
            "forty dollars per hour",
        )

    def test_booking_id_expansion(self):
        """Validates that booking and reservation IDs are spelled out clearly."""
        self.assertEqual(normalize_speech_text("BK-492"), "B K 4 9 2")
        self.assertEqual(normalize_speech_text("BK-A1B2"), "B K A 1 B 2")
        self.assertEqual(normalize_speech_text("CONF-7890"), "C O N F 7 8 9 0")

    def test_room_code_expansion(self):
        """Validates room code expansion."""
        self.assertEqual(normalize_speech_text("R-101"), "room 1 0 1")
        self.assertEqual(normalize_speech_text("R-204"), "room 2 0 4")

    def test_date_expansion(self):
        """Validates ISO 8601 date expansion into spoken English."""
        self.assertEqual(normalize_speech_text("2026-11-14"), "November 14th, 2026")
        self.assertEqual(normalize_speech_text("2026-01-01"), "January 1st, 2026")
        self.assertEqual(normalize_speech_text("2026-07-23"), "July 23rd, 2026")

    def test_abbreviations(self):
        """Validates spoken abbreviation expansion."""
        self.assertIn("approximately", normalize_speech_text("approx. 10 mins."))
        self.assertIn("minutes", normalize_speech_text("5 mins."))
        self.assertIn("hours", normalize_speech_text("2 hrs."))
        self.assertIn("with", normalize_speech_text("room w/ ocean view"))

    def test_composite_booking_sentence(self):
        """Validates a realistic conversational response containing multiple tokens."""
        raw = "Your reservation BK-492 for Room R-101 on 2026-11-14 is confirmed at $180/night approx."
        normalized = normalize_speech_text(raw)
        self.assertIn("B K 4 9 2", normalized)
        self.assertIn("room 1 0 1", normalized)
        self.assertIn("November 14th, 2026", normalized)
        self.assertIn("one hundred eighty dollars per night", normalized)
        self.assertIn("approximately", normalized)


class TestVoiceCatalog(unittest.TestCase):
    """Tests for voice catalog and metadata registry."""

    def test_native_kokoro_voices_exist(self):
        """Verifies core Kokoro voices are properly registered."""
        sarah = get_voice_profile("af_sarah", provider="kokoro")
        self.assertEqual(sarah.name, "Sarah")
        self.assertEqual(sarah.gender, "female")
        self.assertEqual(sarah.accent, "en-US")
        self.assertIn("hotel_frontdesk", sarah.role_fit)

        adam = get_voice_profile("am_adam", provider="kokoro")
        self.assertEqual(adam.gender, "male")
        self.assertEqual(adam.accent, "en-US")

        emma = get_voice_profile("bf_emma", provider="kokoro")
        self.assertEqual(emma.gender, "female")
        self.assertEqual(emma.accent, "en-GB")

    def test_unknown_voice_fallback(self):
        """Requesting an unknown voice ID must fall back gracefully to default without error."""
        profile = get_voice_profile("non_existent_voice", provider="kokoro")
        self.assertEqual(profile.voice_id, "af_sarah")

    def test_list_available_voices_filtering(self):
        """Tests filtering catalog by provider and gender."""
        kokoro_females = list_available_voices(provider="kokoro", gender="female")
        self.assertTrue(len(kokoro_females) >= 3)
        for v in kokoro_females:
            self.assertEqual(v.provider, "kokoro")
            self.assertEqual(v.gender, "female")

        kokoro_males = list_available_voices(provider="kokoro", gender="male")
        self.assertTrue(len(kokoro_males) >= 2)
        for v in kokoro_males:
            self.assertEqual(v.provider, "kokoro")
            self.assertEqual(v.gender, "male")

    def test_default_voice_for_role(self):
        """Tests role-based default voice selection."""
        frontdesk = get_default_voice_for_role("hotel_frontdesk", provider="kokoro", gender="female")
        self.assertEqual(frontdesk.voice_id, "af_sarah")

        room_service = get_default_voice_for_role("room_service", provider="kokoro", gender="male")
        self.assertEqual(room_service.voice_id, "am_adam")


class TestVoiceController(unittest.TestCase):
    """Tests for dynamic in-call acoustic parameter management and command parsing."""

    def test_speed_adjustment_and_clamping(self):
        """Validates speed delta changes and boundary clamping [0.70, 1.40]."""
        controller = VoiceController(speed=1.00)
        self.assertEqual(controller.adjust_speed(0.15), 1.15)
        self.assertEqual(controller.adjust_speed(-0.30), 0.85)

        # Clamping at max
        controller.adjust_speed(1.00)
        self.assertEqual(controller.speed, MAX_SPEED)

        # Clamping at min
        controller.adjust_speed(-2.00)
        self.assertEqual(controller.speed, MIN_SPEED)

    def test_pitch_adjustment_and_clamping(self):
        """Validates pitch delta changes and boundary clamping [-20.0, +20.0]."""
        controller = VoiceController(pitch=0.0)
        self.assertEqual(controller.adjust_pitch(5.0), 5.0)
        self.assertEqual(controller.adjust_pitch(-10.0), -5.0)

        # Clamping at max
        controller.adjust_pitch(50.0)
        self.assertEqual(controller.pitch, MAX_PITCH)

        # Clamping at min
        controller.adjust_pitch(-100.0)
        self.assertEqual(controller.pitch, MIN_PITCH)

    def test_switch_voice(self):
        """Validates manual voice switching."""
        controller = VoiceController(voice_id="af_sarah", provider="kokoro")
        self.assertEqual(controller.voice_id, "af_sarah")

        controller.switch_voice("bf_emma")
        self.assertEqual(controller.voice_id, "bf_emma")
        self.assertEqual(controller.profile.accent, "en-GB")

    def test_switch_gender(self):
        """Validates switching gender to male and female."""
        controller = VoiceController(voice_id="af_sarah", provider="kokoro")
        self.assertEqual(controller.profile.gender, "female")

        controller.switch_gender("male")
        self.assertEqual(controller.profile.gender, "male")
        self.assertIn(controller.voice_id, ("am_adam", "am_michael", "bm_george"))

        controller.switch_gender("female")
        self.assertEqual(controller.profile.gender, "female")

    def test_verbal_command_speak_slower(self):
        """Caller saying 'speak slower' must decrease speed and return affirmative ack."""
        controller = VoiceController(speed=1.00)
        res = controller.parse_voice_command("Could you please speak a little slower?")
        self.assertIsNotNone(res)
        self.assertEqual(res["action"], "adjust_speed")
        self.assertEqual(controller.speed, 0.85)
        self.assertIn("slower", res["spoken_ack"])

    def test_verbal_command_speak_faster(self):
        """Caller saying 'speak faster' must increase speed."""
        controller = VoiceController(speed=1.00)
        res = controller.parse_voice_command("Please talk faster, I'm in a hurry.")
        self.assertIsNotNone(res)
        self.assertEqual(res["action"], "adjust_speed")
        self.assertEqual(controller.speed, 1.15)
        self.assertIn("pace", res["spoken_ack"])

    def test_verbal_command_switch_male(self):
        """Caller saying 'switch to a male voice' swaps gender."""
        controller = VoiceController(voice_id="af_sarah", provider="kokoro")
        res = controller.parse_voice_command("Can I talk to a male voice?")
        self.assertIsNotNone(res)
        self.assertEqual(res["action"], "switch_voice")
        self.assertEqual(controller.profile.gender, "male")

    def test_verbal_command_unrelated_speech_returns_none(self):
        """Regular booking dialogue does not trigger voice changes."""
        controller = VoiceController()
        res = controller.parse_voice_command("I'd like to book a deluxe room for two nights.")
        self.assertIsNone(res)

    def test_settings_delta_payload(self):
        """Validates dictionary representation for settings updates."""
        controller = VoiceController(voice_id="am_adam", speed=1.10, pitch=2.0)
        delta = controller.get_settings_delta()
        self.assertEqual(delta["voice"], "am_adam")
        self.assertEqual(delta["speed"], 1.10)
        self.assertEqual(delta["pitch"], 2.0)


if __name__ == "__main__":
    unittest.main()
