#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import NoReturn, TextIO, cast

ISSUE_RE = re.compile(r"MODEL-(?:SHELL|SDD|RUN|PLAN)-\d{2}")


class AuditError(Exception):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AuditError("USAGE", message)


def json_value(text: str, label: str) -> object:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise AuditError("JSON", f"{label}: duplicate key {key}")
            result[key] = value
        return result

    def reject_constant(value: str) -> NoReturn:
        raise AuditError("JSON", f"{label}: invalid constant {value}")

    try:
        value: object = json.loads(
            text,
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (ValueError, RecursionError) as exc:
        raise AuditError("JSON", f"{label}: invalid JSON") from exc
    return value


def json_object(text: str, label: str) -> dict[str, object]:
    value = json_value(text, label)
    if not isinstance(value, dict):
        raise AuditError("SCHEMA", f"{label}: expected object")
    return cast(dict[str, object], value)


def text_field(event: dict[str, object], key: str) -> str:
    value = event[key]
    if not isinstance(value, str) or not value or value != value.strip():
        raise AuditError("SCHEMA", f"{key}: expected nonblank trimmed string")
    return value


def int_field(event: dict[str, object], key: str) -> int:
    value = event[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise AuditError("SCHEMA", f"{key}: expected integer")
    return value


def issues(event: dict[str, object]) -> tuple[str, ...]:
    value = event["issue_ids"]
    if not isinstance(value, list):
        raise AuditError("SCHEMA", "issue_ids: expected array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or ISSUE_RE.fullmatch(item) is None:
            raise AuditError("SCHEMA", "issue_ids: invalid issue ID")
        result.append(item)
    if len(result) != len(set(result)):
        raise AuditError("SCHEMA", "issue_ids: duplicate issue ID")
    return tuple(result)


def internal_ms(event: dict[str, object]) -> None:
    if "internal_ms" not in event:
        return
    value = event["internal_ms"]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise AuditError("SCHEMA", "internal_ms: expected JSON number")
    if value < 0 or (isinstance(value, float) and (value != value or value == float("inf"))):
        raise AuditError("SCHEMA", "internal_ms: expected finite nonnegative number")


def validate_event(event: dict[str, object]) -> None:
    identity = {"event_id", "kind", "scope", "stage", "attempt", "recovery_of"}
    kind = event.get("kind")
    if kind == "start":
        required = identity
        allowed = required
    elif kind == "end":
        required = identity | {"outcome", "issue_ids"}
        allowed = required | {"symptom", "first_hypothesis", "internal_ms"}
    else:
        raise AuditError("SCHEMA", "kind: expected start or end")

    missing = required - set(event)
    unknown = set(event) - allowed
    if missing:
        raise AuditError("SCHEMA", f"missing: {','.join(sorted(missing))}")
    if unknown:
        raise AuditError("SCHEMA", f"unknown: {','.join(sorted(unknown))}")

    event_id = text_field(event, "event_id")
    scope = text_field(event, "scope")
    if scope not in {"task", "stage", "call"}:
        raise AuditError("SCHEMA", "scope: expected task, stage, or call")
    text_field(event, "stage")
    attempt = int_field(event, "attempt")
    if attempt < 0:
        raise AuditError("SCHEMA", "attempt: expected nonnegative integer")

    recovery = event["recovery_of"]
    if recovery is not None:
        if not isinstance(recovery, str) or not recovery or recovery != recovery.strip():
            raise AuditError("SCHEMA", "recovery_of: expected null or nonblank string")
        if recovery == event_id:
            raise AuditError("SCHEMA", "recovery_of cannot reference itself")
    if recovery is None and attempt != 0:
        raise AuditError("SCHEMA", "original event must use attempt 0")
    if recovery is not None and attempt == 0:
        raise AuditError("SCHEMA", "recovery event must use positive attempt")

    if kind == "start":
        return

    outcome = text_field(event, "outcome")
    if outcome not in {"pass", "fail", "deviation"}:
        raise AuditError("SCHEMA", "outcome: expected pass, fail, or deviation")
    event_issues = issues(event)
    if (outcome in {"fail", "deviation"} or recovery is not None) and not event_issues:
        raise AuditError("SCHEMA", "fail, deviation, or recovery requires issue_ids")
    internal_ms(event)

    has_symptom = "symptom" in event
    has_hypothesis = "first_hypothesis" in event
    if outcome == "fail":
        if not has_symptom or not has_hypothesis:
            raise AuditError("SCHEMA", "failed end requires symptom and first_hypothesis")
        text_field(event, "symptom")
        text_field(event, "first_hypothesis")
    elif has_symptom or has_hypothesis:
        raise AuditError("SCHEMA", "non-failed end cannot have error fields")


def check_next(
    event: dict[str, object],
    opened: dict[str, dict[str, object]],
    completed: dict[str, dict[str, object]],
) -> None:
    event_id = text_field(event, "event_id")
    scope = text_field(event, "scope")
    task_open = any(item["scope"] == "task" for item in opened.values())
    if event["kind"] == "start":
        if event_id in opened or event_id in completed:
            raise AuditError("JOURNAL", "duplicate event_id")
        if scope == "task":
            if opened or completed:
                raise AuditError("JOURNAL", "task start must be the first event")
        elif not task_open:
            raise AuditError("JOURNAL", "non-task event must be inside task envelope")
        recovery = event["recovery_of"]
        if recovery is not None:
            failed = completed.get(cast(str, recovery))
            if failed is None:
                raise AuditError("JOURNAL", "recovery must follow a completed failure")
            if failed["outcome"] != "fail":
                raise AuditError("JOURNAL", "recovery_of must reference failure")
            if int_field(event, "attempt") != int_field(failed, "attempt") + 1:
                raise AuditError("JOURNAL", "recovery attempt must increment")
        return

    start = opened.get(event_id)
    if start is None:
        raise AuditError("JOURNAL", "end has no preceding start")
    if scope == "task" and len(opened) != 1:
        raise AuditError("JOURNAL", "task end must follow all enclosed events")
    if any(
        event[key] != start[key]
        for key in ("scope", "stage", "attempt", "recovery_of")
    ):
        raise AuditError("JOURNAL", "start/end identity fields differ")
    recovery = start["recovery_of"]
    if recovery is not None and issues(event) != issues(completed[cast(str, recovery)]):
        raise AuditError("JOURNAL", "recovery end issue_ids differ from failure")


def accept_next(
    event: dict[str, object],
    opened: dict[str, dict[str, object]],
    completed: dict[str, dict[str, object]],
) -> None:
    event_id = text_field(event, "event_id")
    if event["kind"] == "start":
        opened[event_id] = event
    else:
        del opened[event_id]
        completed[event_id] = event


def new_output(raw_path: str) -> TextIO:
    if not raw_path or "\x00" in raw_path or raw_path.endswith(os.sep):
        raise AuditError("OUTPUT", "invalid output path")
    path = os.path.abspath(raw_path)
    parent, name = os.path.split(path)
    if os.path.realpath(parent) != parent:
        raise AuditError("OUTPUT", "output parent path contains a symlink")
    if not name or name in {".", ".."}:
        raise AuditError("OUTPUT", "invalid output basename")

    try:
        before = os.lstat(parent)
    except OSError as exc:
        raise AuditError("OUTPUT", "output parent unavailable") from exc
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
        or before.st_uid != os.getuid()
        or stat.S_IMODE(before.st_mode) != 0o700
    ):
        raise AuditError("OUTPUT", "parent must be owned, non-symlink, mode 0700")

    parent_fd = -1
    output_fd = -1
    try:
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        after = os.fstat(parent_fd)
        if (
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or after.st_uid != os.getuid()
            or not stat.S_ISDIR(after.st_mode)
            or stat.S_IMODE(after.st_mode) != 0o700
        ):
            raise AuditError("OUTPUT", "output parent changed")
        output_fd = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        os.fchmod(output_fd, 0o600)
        info = os.fstat(output_fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise AuditError("OUTPUT", "new output failed safety checks")
        handle = cast(
            TextIO,
            open(output_fd, "w", encoding="utf-8", newline="\n", closefd=True),
        )
        output_fd = -1
        return handle
    except AuditError:
        raise
    except OSError as exc:
        raise AuditError("OUTPUT", "target must be new and non-symlink") from exc
    finally:
        if output_fd >= 0:
            os.close(output_fd)
        if parent_fd >= 0:
            os.close(parent_fd)


def record(output: str) -> dict[str, object]:
    clock_id = str(uuid.uuid4())
    opened: dict[str, dict[str, object]] = {}
    completed: dict[str, dict[str, object]] = {}
    count = 0
    previous_utc: datetime | None = None
    previous_monotonic: int | None = None

    with new_output(output) as handle:
        for line_number, line in enumerate(sys.stdin, 1):
            if not line.strip():
                raise AuditError("SCHEMA", f"line {line_number}: blank")
            event = json_object(line, f"line {line_number}")
            validate_event(event)
            check_next(event, opened, completed)
            now = datetime.now(timezone.utc)
            monotonic_ns = time.monotonic_ns()
            if previous_utc is not None and now <= previous_utc:
                raise AuditError("CLOCK", "UTC clock did not advance")
            if previous_monotonic is not None and monotonic_ns <= previous_monotonic:
                raise AuditError("CLOCK", "monotonic clock did not advance")

            count += 1
            payload = dict(event)
            payload.update(
                {
                    "clock_id": clock_id,
                    "recorded_at_utc": now.isoformat(timespec="microseconds").replace(
                        "+00:00", "Z"
                    ),
                    "monotonic_ns": monotonic_ns,
                    "sequence": count,
                }
            )
            handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            accept_next(event, opened, completed)
            previous_utc = now
            previous_monotonic = monotonic_ns

    if count == 0:
        raise AuditError("JOURNAL", "no events recorded")
    if opened:
        raise AuditError("JOURNAL", "recording ended with unpaired starts")
    if sum(item["scope"] == "task" for item in completed.values()) != 1:
        raise AuditError("JOURNAL", "expected exactly one task envelope")
    return {"status": "ok", "clock_id": clock_id, "events": count}


def parser() -> Parser:
    result = Parser()
    subcommands = result.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("record")
    command.add_argument("--output", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        result = record(cast(str, args.output))
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except AuditError as exc:
        print(f"ERROR[{exc.category}]: {str(exc).replace(chr(10), ' ')}", file=sys.stderr)
        return 1
    except OSError:
        print("ERROR[IO]: operating-system I/O failure", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
