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
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import NoReturn, TextIO, cast

ISSUE_RE = re.compile(r"MODEL-(?:SHELL|SDD|RUN|PLAN)-\d{2}")
UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z")
WALL_RE = re.compile(r"(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
TOOL_HEADING = "## Tool results"
TABLE_HEADER = (
    "| Ordinal | Tool | Outcome | Wall ms | Observed shape | Retry count | Issue ID |"
)
TABLE_SEPARATOR = "|---:|---|---|---:|---|---:|---|"
GENERATED = {"clock_id", "recorded_at_utc", "monotonic_ns", "sequence"}


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


def read_owned_regular(raw_path: str, label: str) -> str:
    try:
        before = os.lstat(raw_path)
    except OSError as exc:
        raise AuditError("INPUT", f"{label}: unavailable") from exc
    if (
        stat.S_ISLNK(before.st_mode)
        or not stat.S_ISREG(before.st_mode)
        or before.st_uid != os.getuid()
    ):
        raise AuditError("INPUT", f"{label}: expected owned non-symlink regular file")

    fd = -1
    try:
        fd = os.open(raw_path, os.O_RDONLY | os.O_NOFOLLOW)
        after = os.fstat(fd)
        if (
            (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
            or after.st_uid != os.getuid()
            or not stat.S_ISREG(after.st_mode)
        ):
            raise AuditError("INPUT", f"{label}: changed while opening")
        with open(fd, "rb", closefd=True) as handle:
            fd = -1
            payload = handle.read()
    except AuditError:
        raise
    except OSError as exc:
        raise AuditError("INPUT", f"{label}: unsafe open failed") from exc
    finally:
        if fd >= 0:
            os.close(fd)
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditError("INPUT", f"{label}: expected UTF-8") from exc


def catalog(text: str, label: str) -> Counter[str]:
    value = json_value(text, label)
    if not isinstance(value, list) or not value:
        raise AuditError("CATALOG", f"{label}: expected nonempty array")
    names: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item or item != item.strip():
            raise AuditError("CATALOG", f"{label}: invalid name")
        names.append(item)
    if len(names) != len(set(names)):
        raise AuditError("CATALOG", f"{label}: duplicate name")
    return Counter(names)


def code_cell(cell: str, label: str) -> str:
    if (
        len(cell) < 3
        or cell[0] != "`"
        or cell[-1] != "`"
        or "`" in cell[1:-1]
        or not cell[1:-1]
        or cell[1:-1] != cell[1:-1].strip()
    ):
        raise AuditError("TABLE", f"{label}: invalid code cell")
    return cell[1:-1]


def table_issues(cell: str) -> tuple[str, ...]:
    if cell == "none":
        return ()
    result: list[str] = []
    for part in cell.split(";"):
        issue = code_cell(part.strip(), "issue")
        if ISSUE_RE.fullmatch(issue) is None:
            raise AuditError("TABLE", "issue: invalid ID")
        result.append(issue)
    if len(result) != len(set(result)):
        raise AuditError("TABLE", "issue: duplicate ID")
    return tuple(result)


def tool_table(text: str) -> Counter[str]:
    lines = text.splitlines()
    headings = [index for index, line in enumerate(lines) if line == TOOL_HEADING]
    if len(headings) != 1:
        raise AuditError("TABLE", "expected one exact Tool results heading")
    if lines.count(TABLE_HEADER) != 1:
        raise AuditError("TABLE", "expected one exact seven-column header")
    section_start = headings[0] + 1
    section_end = next(
        (
            index
            for index in range(section_start, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    headers = [
        index
        for index in range(section_start, section_end)
        if lines[index] == TABLE_HEADER
    ]
    if len(headers) != 1:
        raise AuditError("TABLE", "header is outside Tool results section")
    header = headers[0]
    if header + 1 >= section_end or lines[header + 1] != TABLE_SEPARATOR:
        raise AuditError("TABLE", "invalid separator")
    if any(line.startswith("|") for line in lines[section_start:header]):
        raise AuditError("TABLE", "unexpected table before tool table")

    tools: list[str] = []
    expected = 1
    cursor = header + 2
    while cursor < section_end and lines[cursor].startswith("|"):
        line = lines[cursor]
        if not line.endswith("|"):
            raise AuditError("TABLE", "row lacks final separator")
        cells = [part.strip() for part in line[1:-1].split("|")]
        if len(cells) != 7 or any(not cell for cell in cells):
            raise AuditError("TABLE", "row must contain seven nonblank cells")
        ordinal, tool_cell, outcome, wall_cell, shape, retry_cell, issue_cell = cells
        if not ordinal.isdecimal() or ordinal != str(expected):
            raise AuditError("TABLE", "ordinals must be canonical 1..N")
        tool = code_cell(tool_cell, "tool")
        if outcome not in {"pass", "pass_with_recovery", "pass_with_deviation"}:
            raise AuditError("TABLE", "invalid outcome")
        if WALL_RE.fullmatch(wall_cell) is None or float(wall_cell) == float("inf"):
            raise AuditError("TABLE", "wall time must be finite and nonnegative")
        if not shape:
            raise AuditError("TABLE", "blank observed shape")
        if not retry_cell.isdecimal() or retry_cell != str(int(retry_cell)):
            raise AuditError("TABLE", "invalid retry count")
        retry = int(retry_cell)
        row_issues = table_issues(issue_cell)
        if outcome == "pass_with_recovery":
            if retry < 1 or not row_issues:
                raise AuditError("TABLE", "recovery requires retry and issue ID")
        elif retry != 0:
            raise AuditError("TABLE", "non-recovery retry must be zero")
        if outcome == "pass_with_deviation" and not row_issues:
            raise AuditError("TABLE", "deviation requires issue ID")
        tools.append(tool)
        expected += 1
        cursor += 1

    if not tools:
        raise AuditError("TABLE", "tool table has no rows")
    if any(line.startswith("|") for line in lines[cursor:section_end]):
        raise AuditError("TABLE", "multiple tables in Tool results section")
    if len(tools) != len(set(tools)):
        raise AuditError("TABLE", "duplicate tool row")
    return Counter(tools)


def recorded_event(
    obj: dict[str, object],
) -> tuple[dict[str, object], str, datetime, int, int]:
    missing = GENERATED - set(obj)
    if missing:
        raise AuditError("SCHEMA", f"missing generated: {','.join(sorted(missing))}")
    client = {key: value for key, value in obj.items() if key not in GENERATED}
    validate_event(client)
    clock_id = text_field(obj, "clock_id")
    try:
        parsed = uuid.UUID(clock_id)
    except ValueError as exc:
        raise AuditError("CLOCK", "clock_id: invalid UUID") from exc
    if str(parsed) != clock_id or parsed.version != 4:
        raise AuditError("CLOCK", "clock_id: expected canonical UUID4")
    utc_text = text_field(obj, "recorded_at_utc")
    if UTC_RE.fullmatch(utc_text) is None:
        raise AuditError("CLOCK", "recorded_at_utc: invalid format")
    try:
        utc = datetime.strptime(utc_text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise AuditError("CLOCK", "recorded_at_utc: invalid value") from exc
    monotonic_ns = int_field(obj, "monotonic_ns")
    sequence = int_field(obj, "sequence")
    if monotonic_ns < 0 or sequence < 1:
        raise AuditError("CLOCK", "invalid monotonic_ns or sequence")
    return client, clock_id, utc, monotonic_ns, sequence


def journal(text: str) -> tuple[int, str]:
    lines = text.splitlines()
    if not lines:
        raise AuditError("JOURNAL", "journal is empty")
    opened: dict[str, dict[str, object]] = {}
    completed: dict[str, dict[str, object]] = {}
    starts: dict[str, tuple[datetime, int]] = {}
    clock_id: str | None = None
    previous_utc: datetime | None = None
    previous_monotonic: int | None = None
    for expected, line in enumerate(lines, 1):
        if not line.strip():
            raise AuditError("JOURNAL", "blank journal line")
        event, current_clock, utc, monotonic_ns, sequence = recorded_event(
            json_object(line, f"journal line {expected}")
        )
        if sequence != expected:
            raise AuditError("JOURNAL", "sequence differs from line order")
        if clock_id is None:
            clock_id = current_clock
        elif current_clock != clock_id:
            raise AuditError("CLOCK", "mixed clock IDs")
        if previous_utc is not None and utc <= previous_utc:
            raise AuditError("CLOCK", "UTC timestamps are not increasing")
        if previous_monotonic is not None and monotonic_ns <= previous_monotonic:
            raise AuditError("CLOCK", "monotonic timestamps are not increasing")
        check_next(event, opened, completed)
        event_id = text_field(event, "event_id")
        if event["kind"] == "start":
            starts[event_id] = (utc, monotonic_ns)
        else:
            start_utc, start_monotonic = starts[event_id]
            if utc <= start_utc or monotonic_ns <= start_monotonic:
                raise AuditError("CLOCK", "nonpositive event duration")
        accept_next(event, opened, completed)
        previous_utc = utc
        previous_monotonic = monotonic_ns
    if opened:
        raise AuditError("JOURNAL", "unpaired start")
    assert clock_id is not None
    return len(lines), clock_id


def validate(args: argparse.Namespace) -> dict[str, object]:
    journal_text = read_owned_regular(cast(str, args.journal), "journal")
    audit_text = read_owned_regular(cast(str, args.audit), "audit")
    live = catalog(
        read_owned_regular(cast(str, args.live_catalog), "live catalog"), "live catalog"
    )
    source = catalog(
        read_owned_regular(cast(str, args.source_catalog), "source catalog"),
        "source catalog",
    )
    config = catalog(
        read_owned_regular(cast(str, args.config_catalog), "config catalog"),
        "config catalog",
    )
    if live != source or live != config:
        raise AuditError("CATALOG", "catalog counters differ")
    table = tool_table(audit_text)
    if table != live:
        raise AuditError("TABLE", "tool table differs from catalogs")
    events, clock_id = journal(journal_text)
    return {
        "status": "ok",
        "catalog_count": sum(live.values()),
        "tool_rows": sum(table.values()),
        "clock_id": clock_id,
        "events": events,
    }


def parser() -> Parser:
    result = Parser()
    subcommands = result.add_subparsers(dest="command", required=True)
    command = subcommands.add_parser("record")
    command.add_argument("--output", required=True)
    command = subcommands.add_parser("validate")
    command.add_argument("--journal", required=True)
    command.add_argument("--audit", required=True)
    command.add_argument("--live-catalog", required=True)
    command.add_argument("--source-catalog", required=True)
    command.add_argument("--config-catalog", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.command == "record":
            result = record(cast(str, args.output))
        else:
            result = validate(args)
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
