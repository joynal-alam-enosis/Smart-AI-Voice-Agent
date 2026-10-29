"""Out-loud confirmation gate for destructive and commercial tool writes."""

from __future__ import annotations

import re
from typing import Any

CONFIRM_PATTERN = re.compile(
    r"\b(yes|yeah|yep|yup|sure|correct|confirmed|confirm|okay|ok|go ahead|"
    r"do it|book it|that'?s right|sounds good|absolutely)\b",
    re.IGNORECASE,
)

MAX_CONFIRMATION_WORDS = 8


def user_confirms(last_user_message: str | None) -> bool:
    """Return True only for a short, explicit spoken confirmation.

    Long utterances are treated as new requests, never as a yes.
    """
    if not last_user_message:
        return False
    text = last_user_message.strip()
    if not text:
        return False
    if len(text.split()) > MAX_CONFIRMATION_WORDS:
        return False
    return bool(CONFIRM_PATTERN.search(text))


def confirmation_granted(
    pending: dict[str, Any] | None,
    kind: str,
    payload: dict[str, Any],
    last_user_message: str | None,
) -> bool:
    """Allow a write only when pending args match and the caller confirmed.

    The first invocation always stages ``pending``. A bare "yes" with no
    matching pending action never commits a booking, order, or cancel.
    """
    if not pending:
        return False
    if pending.get("kind") != kind:
        return False
    if pending.get("payload") != payload:
        return False
    return user_confirms(last_user_message)
