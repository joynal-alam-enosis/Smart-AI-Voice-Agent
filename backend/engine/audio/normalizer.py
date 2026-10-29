"""Speech Text Normalizer Pre-Processor.

Expands conversational text (currencies, booking reference codes, room IDs,
dates, and abbreviations) into natural, phonetically pronounceable text for TTS.
"""

from __future__ import annotations

import re

# Word maps for number to words expansion
ONES = [
    "", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen"
]
TENS = [
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"
]

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April", 5: "May", 6: "June",
    7: "July", 8: "August", 9: "September", 10: "October", 11: "November", 12: "December"
}

ORDINAL_SUFFIX = {
    1: "st", 2: "nd", 3: "rd", 21: "st", 22: "nd", 23: "rd", 31: "st"
}

ABBREVIATIONS = {
    r"\bapprox\b\.?": "approximately",
    r"\bapt\b\.?": "apartment",
    r"\bdept\b\.?": "department",
    r"\bmins\b\.?": "minutes",
    r"\bmin\b\.?": "minutes",
    r"\bhrs\b\.?": "hours",
    r"\bhr\b\.?": "hours",
    r"\bw/o(?=\s|$)": "without",
    r"\bw/(?=\s|$)": "with",
    r"\bvs\b\.?": "versus",
    r"\betc\b\.?": "et cetera",
    r"\bno\b\.(?=\s*[0-9])": "number",
}


def int_to_words(n: int) -> str:
    """Converts an integer between 0 and 999,999,999 to English words."""
    if n == 0:
        return "zero"
    if n < 0:
        return f"negative {int_to_words(abs(n))}"

    parts: list[str] = []

    millions = n // 1_000_000
    remainder = n % 1_000_000

    if millions > 0:
        parts.append(f"{_hundreds_to_words(millions)} million")

    thousands = remainder // 1000
    remainder = remainder % 1000

    if thousands > 0:
        parts.append(f"{_hundreds_to_words(thousands)} thousand")

    if remainder > 0:
        parts.append(_hundreds_to_words(remainder))

    return " ".join(parts).strip()


def _hundreds_to_words(n: int) -> str:
    """Helper for converting 1-999 to words."""
    parts = []
    hundreds = n // 100
    rest = n % 100

    if hundreds > 0:
        parts.append(f"{ONES[hundreds]} hundred")

    if rest > 0:
        if rest < 20:
            parts.append(ONES[rest])
        else:
            ten = rest // 10
            one = rest % 10
            if one > 0:
                parts.append(f"{TENS[ten]}-{ONES[one]}")
            else:
                parts.append(TENS[ten])

    return " ".join(parts)


def _expand_currency(match: re.Match) -> str:
    """Expands currency tokens like $180, $250.50, $180/night."""
    full_str = match.group(0)
    dollars_str = match.group(1).replace(",", "")
    cents_str = match.group(2)
    suffix = match.group(3) or ""

    try:
        dollars = int(dollars_str)
    except ValueError:
        return full_str

    cents = int(cents_str) if cents_str else 0

    parts = []
    if dollars == 1:
        parts.append("one dollar")
    elif dollars > 0 or cents == 0:
        parts.append(f"{int_to_words(dollars)} dollars")

    if cents > 0:
        cents_words = int_to_words(cents)
        cents_label = "cent" if cents == 1 else "cents"
        if dollars > 0:
            parts.append(f"and {cents_words} {cents_label}")
        else:
            parts.append(f"{cents_words} {cents_label}")

    result = " ".join(parts)
    if suffix in ("/night", "/nt"):
        result += " per night"
    elif suffix in ("/day",):
        result += " per day"
    elif suffix in ("/hr", "/hour"):
        result += " per hour"

    return result


def _expand_booking_id(match: re.Match) -> str:
    """Expands booking reference codes like BK-492, BK-A1B2 into spaced characters."""
    prefix = match.group(1)
    code = match.group(2)
    # Spell out each character in prefix and code with a space
    chars = [c.upper() for c in prefix] + [c.upper() for c in code if c != "-"]
    return " ".join(chars)


def _expand_room_code(match: re.Match) -> str:
    """Expands room codes like R-101, Room 204 into 'room one zero one'."""
    room_num = match.group(1)
    spelled_digits = " ".join(room_num)
    return f"room {spelled_digits}"


def _expand_iso_date(match: re.Match) -> str:
    """Expands ISO 8601 dates (YYYY-MM-DD) into natural date speech."""
    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    month_name = MONTH_NAMES.get(month)
    if not month_name:
        return match.group(0)

    suffix = ORDINAL_SUFFIX.get(day, "th")
    return f"{month_name} {day}{suffix}, {year}"


def _expand_phone(match: re.Match) -> str:
    """Expands US/International phone numbers into grouped spoken digits."""
    digits = re.sub(r"\D", "", match.group(0))
    if len(digits) == 10:
        area = " ".join(digits[:3])
        prefix = " ".join(digits[3:6])
        line = " ".join(digits[6:])
        return f"{area}, {prefix}, {line}"
    elif len(digits) == 11 and digits.startswith("1"):
        country = digits[0]
        area = " ".join(digits[1:4])
        prefix = " ".join(digits[4:7])
        line = " ".join(digits[7:])
        return f"{country}, {area}, {prefix}, {line}"
    return " ".join(digits)


def normalize_speech_text(text: str) -> str:
    """Normalizes raw LLM output text for high-fidelity speech synthesis.

    Transformations:
    - Currency: $180 -> 'one hundred eighty dollars', $180/night -> '... per night'
    - Booking IDs: BK-492 -> 'B K 4 9 2'
    - Room IDs: R-101 -> 'room 1 0 1'
    - Dates: 2026-11-14 -> 'November 14th, 2026'
    - Phone numbers: 555-123-4567 -> grouped digits
    - Common abbreviations: approx. -> approximately, apt. -> apartment
    """
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)

    normalized = text

    # 1. Expand currency: $180, $180.50, $180/night, $180/nt
    currency_pattern = re.compile(
        r"\$([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)(?:\.([0-9]{2}))?(/night|/nt|/day|/hour|/hr)?\b"
    )
    normalized = currency_pattern.sub(_expand_currency, normalized)

    # 2. Expand Booking IDs: BK-492, BK-A1B2C3, CONF-1234
    booking_pattern = re.compile(r"\b(BK|RES|CONF)-([A-Za-z0-9]+)\b")
    normalized = booking_pattern.sub(_expand_booking_id, normalized)

    # 3. Expand Room IDs: Room R-101, R-101, R-204
    room_pattern = re.compile(r"\b(?:Room\s+)?R-([0-9]{3,4})\b", re.IGNORECASE)
    normalized = room_pattern.sub(_expand_room_code, normalized)

    # 4. Expand ISO dates: 2026-11-14
    date_pattern = re.compile(r"\b(20[2-3][0-9])-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])\b")
    normalized = date_pattern.sub(_expand_iso_date, normalized)

    # 5. Expand Phone numbers: (555) 123-4567 or 555-123-4567 or +1-555-123-4567
    phone_pattern = re.compile(r"(?:\+1[-.\s]?)?\(?[0-9]{3}\)?[-.\s][0-9]{3}[-.\s][0-9]{4}\b")
    normalized = phone_pattern.sub(_expand_phone, normalized)

    # 6. Expand Abbreviations
    for pattern, replacement in ABBREVIATIONS.items():
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    # 7. Collapse extra whitespace
    normalized = re.sub(r"\s+", " ", normalized).strip()

    return normalized
