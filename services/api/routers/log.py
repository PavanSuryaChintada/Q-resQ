"""Append-only dispatch ledger. See docs/DESIGN.md #1 - the signature
element. Never UPDATE or DELETE, per schema.sql's comment on
dispatch_log. In-memory for now; swapped for Supabase once wired to
real data.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from models import LogChannel, LogLine

router = APIRouter()

_log: list[LogLine] = []
_next_id = 1


def append(channel: LogChannel, message: str, severity: int = 0) -> LogLine:
    global _next_id
    line = LogLine(id=_next_id, at=datetime.now(timezone.utc), channel=channel,
                    severity=severity, message=message)
    _log.append(line)
    _next_id += 1
    return line


@router.get("", response_model=list[LogLine])
def tail(since: int | None = None) -> list[LogLine]:
    if since is None:
        return list(_log)
    return [line for line in _log if line.id > since]
