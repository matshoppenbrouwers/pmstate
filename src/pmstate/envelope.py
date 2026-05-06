"""CloudEvents-shaped event envelope. Locked field set per design Q1-Q7."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import attrs

from pmstate import _ulid

_TYPE_REGEX = re.compile(r"^pmstate\.[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+(\.v\d+)?$")


def _now_ms_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _validate_type(_inst: Event, _attr: attrs.Attribute[str], value: str) -> None:
    if not _TYPE_REGEX.match(value):
        raise ValueError(
            f"event type {value!r} must match {_TYPE_REGEX.pattern!r} "
            "(e.g. 'pmstate.quote.received' or 'pmstate.quote.received.v2')"
        )


def _validate_source(_inst: Event, _attr: attrs.Attribute[str], value: str) -> None:
    if not value.startswith("/"):
        raise ValueError(f"event source {value!r} must start with '/'")


@attrs.define(frozen=True, slots=True)
class Event:
    """CloudEvents 1.0 JSON envelope. Use :meth:`Event.new` to build one."""

    id: str
    source: str = attrs.field(validator=_validate_source)
    type: str = attrs.field(validator=_validate_type)
    time: str
    specversion: str = "1.0"
    subject: str | None = None
    data: dict[str, Any] | None = None
    causationid: str | None = None

    @classmethod
    def new(
        cls,
        *,
        type: str,
        source: str,
        data: dict[str, Any] | None = None,
        subject: str | None = None,
        causationid: str | None = None,
    ) -> Event:
        """Build a fresh event: generates ``id`` (ULID) and ``time`` (UTC, ms precision)."""
        return cls(
            id=_ulid.new(),
            source=source,
            type=type,
            time=_now_ms_iso(),
            subject=subject,
            data=data,
            causationid=causationid,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a CloudEvents-shaped dict (drops ``None`` optional fields)."""
        out: dict[str, Any] = {
            "specversion": self.specversion,
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "time": self.time,
        }
        if self.subject is not None:
            out["subject"] = self.subject
        if self.data is not None:
            out["data"] = self.data
        if self.causationid is not None:
            out["causationid"] = self.causationid
        return out

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Event:
        """Deserialize from a CloudEvents-shaped dict."""
        return cls(
            id=d["id"],
            source=d["source"],
            type=d["type"],
            time=d["time"],
            specversion=d.get("specversion", "1.0"),
            subject=d.get("subject"),
            data=d.get("data"),
            causationid=d.get("causationid"),
        )
