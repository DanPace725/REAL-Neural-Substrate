from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRACE_ROOT = ROOT / "docs" / "traces"
DEFAULT_JSON_OUTPUT = DEFAULT_TRACE_ROOT / "index.json"
DEFAULT_MD_OUTPUT = DEFAULT_TRACE_ROOT / "INDEX.md"

TRACE_DATE_RE = re.compile(
    r"(?P<year>20\d{2})[-_]?(?P<month>\d{2})[-_]?(?P<day>\d{2})"
    r"(?:[ _-]?(?P<hour>\d{2})(?P<minute>\d{2}))?"
)
TITLE_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$")
INLINE_CODE_RE = re.compile(r"`([^`]+)`")
PATH_RE = re.compile(
    r"(?P<path>"
    r"(?:AGENTS\.md|README\.md|pyproject\.toml|PLAIN_ENGLISH_OVERVIEW\.md|SYNTHESIS\.md|research_paper_draft\.tex)"
    r"|(?:real_core|phase8|scripts|tests|docs|occupancy_baseline)[/\\][^`'\"<>()\[\]\n]+?\.[A-Za-z0-9]+"
    r")"
)
ABSOLUTE_REPO_PATH_RE = re.compile(
    r"REAL-Neural-Substrate[/\\](?P<path>(?:real_core|phase8|scripts|tests|docs|occupancy_baseline)[/\\][^)\]]+?\.[A-Za-z0-9]+)"
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "then",
    "than",
    "when",
    "what",
    "where",
    "which",
    "while",
    "after",
    "before",
    "through",
    "using",
    "used",
    "over",
    "under",
    "does",
    "did",
    "not",
    "now",
    "just",
    "more",
    "most",
    "some",
    "same",
    "been",
    "being",
    "into",
    "onto",
    "they",
    "them",
    "their",
    "there",
    "these",
    "those",
    "only",
    "also",
    "very",
    "still",
    "good",
    "real",
    "phase",
    "session",
    "trace",
    "task",
    "pass",
    "docs",
    "scripts",
    "tests",
    "test",
    "run",
    "runs",
    "file",
    "files",
    "json",
    "md",
    "py",
    "html",
}


@dataclass
class TraceEntry:
    path: str
    filename: str
    title: str
    timestamp: str | None
    trace_date: str | None
    trace_type: str | None
    author: str | None
    model: str | None
    keywords: list[str]
    referenced_files: list[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "filename": self.filename,
            "title": self.title,
            "timestamp": self.timestamp,
            "date": self.trace_date,
            "trace_type": self.trace_type,
            "author": self.author,
            "model": self.model,
            "keywords": self.keywords,
            "referenced_files": self.referenced_files,
        }


def _normalize_path(value: str) -> str:
    value = value.strip().strip(".,:;)")
    return value.replace("\\", "/")


def _relative_repo_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return _normalize_path(str(resolved.relative_to(ROOT)))
    except ValueError:
        return _normalize_path(str(path))


def _extract_timestamp(value: str) -> tuple[str | None, str | None]:
    match = TRACE_DATE_RE.search(value)
    if not match:
        return None, None
    year = int(match.group("year"))
    month = int(match.group("month"))
    day = int(match.group("day"))
    hour = match.group("hour")
    minute = match.group("minute")
    if hour is not None and minute is not None:
        dt = datetime(year, month, day, int(hour), int(minute))
        return dt.isoformat(timespec="minutes"), dt.date().isoformat()
    dt = datetime(year, month, day)
    return dt.date().isoformat(), dt.date().isoformat()


def _extract_title(lines: list[str], fallback: str) -> str:
    for line in lines[:10]:
        match = TITLE_RE.match(line.strip())
        if match:
            return match.group("title").strip()
    return fallback


def _extract_field(lines: list[str], *labels: str) -> str | None:
    normalized_labels = tuple(label.lower().rstrip(":") for label in labels)
    for line in lines[:20]:
        stripped = line.strip()
        lowered = stripped.lower().replace("*", "")
        for label in normalized_labels:
            cleaned_label = label.replace("*", "")
            if lowered.startswith(cleaned_label):
                _, _, value = stripped.partition(":")
                value = value.strip().strip("*").strip()
                return value or None
    return None


def _extract_referenced_files(text: str) -> list[str]:
    found: set[str] = set()
    for match in ABSOLUTE_REPO_PATH_RE.finditer(text):
        found.add(_normalize_path(match.group("path")))
    for match in PATH_RE.finditer(text):
        found.add(_normalize_path(match.group("path")))
    return sorted(found)


def _extract_keywords(
    *,
    title: str,
    trace_type: str | None,
    author: str | None,
    model: str | None,
    referenced_files: Iterable[str],
    lines: list[str],
    limit: int = 12,
) -> list[str]:
    counts: dict[str, int] = defaultdict(int)
    sources = [title]
    for value in (trace_type, author, model):
        if value:
            sources.append(value)
    sources.extend(lines[:30])
    for source in sources:
        for word in WORD_RE.findall(source):
            normalized = word.lower()
            if normalized in STOPWORDS:
                continue
            if normalized.startswith("2026"):
                continue
            counts[normalized] += 1
    for path in referenced_files:
        for part in WORD_RE.findall(path):
            normalized = part.lower()
            if normalized in STOPWORDS or normalized.isdigit():
                continue
            counts[normalized] += 2
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


def parse_trace(path: Path, trace_root: Path) -> TraceEntry:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    text = "\n".join(lines)
    title = _extract_title(lines, path.stem)
    timestamp, trace_date = _extract_timestamp(path.name)
    if timestamp is None:
        timestamp, trace_date = _extract_timestamp(title)
    trace_type = _extract_field(lines, "**Type**", "**Session type**", "Type")
    author = _extract_field(lines, "**Author**", "Author")
    model = _extract_field(lines, "**Model**", "Model")
    referenced_files = _extract_referenced_files(text)
    keywords = _extract_keywords(
        title=title,
        trace_type=trace_type,
        author=author,
        model=model,
        referenced_files=referenced_files,
        lines=lines,
    )
    return TraceEntry(
        path=_relative_repo_path(path),
        filename=path.name,
        title=title,
        timestamp=timestamp,
        trace_date=trace_date,
        trace_type=trace_type,
        author=author,
        model=model,
        keywords=keywords,
        referenced_files=referenced_files,
    )


def build_index(trace_root: Path) -> dict[str, object]:
    entries = [
        parse_trace(path, trace_root)
        for path in sorted(trace_root.glob("*.md"))
        if path.name.lower() != "index.md"
    ]
    entries.sort(
        key=lambda entry: (
            entry.timestamp or "",
            entry.filename,
        ),
        reverse=True,
    )

    by_keyword: dict[str, list[str]] = defaultdict(list)
    by_file: dict[str, list[str]] = defaultdict(list)
    for entry in entries:
        for keyword in entry.keywords:
            by_keyword[keyword].append(entry.path)
        for ref in entry.referenced_files:
            by_file[ref].append(entry.path)

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "trace_root": _relative_repo_path(trace_root),
        "entry_count": len(entries),
        "entries": [entry.as_dict() for entry in entries],
        "by_keyword": {key: sorted(set(paths)) for key, paths in sorted(by_keyword.items())},
        "by_file": {key: sorted(set(paths)) for key, paths in sorted(by_file.items())},
    }


def render_markdown(index: dict[str, object]) -> str:
    entries = list(index["entries"])
    by_keyword: dict[str, list[str]] = dict(index["by_keyword"])
    by_file: dict[str, list[str]] = dict(index["by_file"])
    lines = [
        "# Trace Index",
        "",
        f"Generated: `{index['generated_at']}`",
        "",
        f"- trace root: `{index['trace_root']}`",
        f"- entry count: `{index['entry_count']}`",
        "",
        "## Recent Traces",
        "",
        "| Date | Title | Type | Keywords | Files |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in entries:
        path = str(entry["path"])
        title = str(entry["title"])
        trace_type = str(entry.get("trace_type") or "")
        date_value = str(entry.get("timestamp") or entry.get("date") or "")
        keywords = ", ".join(str(word) for word in list(entry.get("keywords") or [])[:5])
        files = len(list(entry.get("referenced_files") or []))
        lines.append(
            f"| `{date_value}` | [{title}](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/{path.replace(' ', '%20')}) | {trace_type} | `{keywords}` | {files} |"
        )

    lines.extend(["", "## Top Keywords", ""])
    keyword_items = sorted(
        by_keyword.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )[:40]
    for keyword, paths in keyword_items:
        lines.append(f"- `{keyword}` ({len(paths)}): " + ", ".join(f"[{Path(path).name}](/C:/Users/nscha/Coding/Relationally%20Embedded%20Allostatic%20Learning/REAL-Neural-Substrate/{path.replace(' ', '%20')})" for path in paths[:4]))

    lines.extend(["", "## Most Referenced Files", ""])
    file_items = sorted(
        by_file.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )[:40]
    for ref, paths in file_items:
        lines.append(f"- `{ref}` ({len(paths)} traces)")

    return "\n".join(lines) + "\n"


def write_index(
    trace_root: Path,
    *,
    json_output: Path,
    markdown_output: Path,
) -> dict[str, object]:
    index = build_index(trace_root)
    json_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    json_output.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    markdown_output.write_text(render_markdown(index), encoding="utf-8")
    return index


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a lightweight trace index for docs/traces."
    )
    parser.add_argument(
        "--trace-root",
        type=Path,
        default=DEFAULT_TRACE_ROOT,
        help="Directory containing markdown trace files.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=DEFAULT_JSON_OUTPUT,
        help="Path to write machine-readable index JSON.",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=DEFAULT_MD_OUTPUT,
        help="Path to write human-readable markdown index.",
    )
    args = parser.parse_args()

    index = write_index(
        args.trace_root,
        json_output=args.output_json,
        markdown_output=args.output_md,
    )
    print(
        f"[trace-index] indexed {index['entry_count']} traces -> "
        f"{args.output_json} and {args.output_md}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
