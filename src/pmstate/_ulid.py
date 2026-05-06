"""ULID generation and validation. Thin wrapper over ``python-ulid``."""

from __future__ import annotations

from ulid import ULID


def new() -> str:
    """Return a fresh 26-char Crockford-base32 ULID."""
    return str(ULID())


def parse(value: str) -> ULID:
    """Parse and validate a ULID string. Raises :class:`ValueError` on malformed input."""
    return ULID.from_str(value)


def is_valid(value: str) -> bool:
    """Return ``True`` iff ``value`` parses as a ULID."""
    try:
        ULID.from_str(value)
    except (ValueError, TypeError):
        return False
    return True
