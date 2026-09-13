"""Streaming XES parser, plus an independent raw event count to verify it against.

The BPI 2017 log is ~1.2M events in a single 30 MB gzipped line, so it is parsed as a stream
with memory bounded to one trace at a time. The parser keeps every lifecycle transition and
leaves values as raw strings; what to keep and how to type it is decided in `normalize.py`, so
changing those choices never requires re-parsing and never loses information here.
"""

from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from meridian.ingestion import schema

# XES attribute element types (IEEE 1849-2016). Only direct children of <trace> and <event> are
# read; nested attributes (children of an attribute) are metadata about that attribute, not
# about the event, so they are ignored by design.
_ATTRIBUTE_TAGS = frozenset(
    {"string", "date", "int", "float", "boolean", "id", "list", "container"}
)

# `<event` followed by whitespace, `>` or `/`, so `<events` or `<eventually>` never match.
_EVENT_OPEN_TAG = re.compile(rb"<event[\s>/]")
_EVENT_OPEN_TAG_BYTES = 7


def _open_binary(path: Path) -> BinaryIO:
    """Open an XES file for binary reading, transparently decompressing `.gz`.

    Why: logs are distributed both compressed and plain; callers should not need to care which.
    """
    return gzip.open(path, "rb") if path.suffix == ".gz" else path.open("rb")


def _local_name(tag: str) -> str:
    """Strip an XML namespace (`{uri}event` becomes `event`).

    Why: some XES writers declare a default namespace, which ElementTree folds into every tag
    name; without stripping, a namespaced file would silently parse as zero events.
    """
    return tag.rsplit("}", 1)[-1]


def count_raw_events(path: Path, chunk_bytes: int = 1 << 20) -> int:
    """Count `<event` open tags by scanning the decompressed bytes, without an XML parser.

    Why a second, independent count: the before/after row-count check must be able to catch the
    parser silently skipping events. If both numbers came from the same parsing logic, a parser
    bug would agree with itself. A byte scan shares no logic with `iter_xes_events`.

    Why the chunk overlap is `pattern length - 1` bytes: a tag split across two chunks is found
    whole in (tail of previous chunk + next chunk), while a complete match can never fit inside
    the overlap alone, so no tag is counted twice. Known limitation: an `<event` inside an XML
    comment would be counted; XES writers do not emit comments inside the log body.
    """
    overlap = _EVENT_OPEN_TAG_BYTES - 1
    total = 0
    tail = b""
    with _open_binary(path) as handle:
        while chunk := handle.read(chunk_bytes):
            buffer = tail + chunk
            total += len(_EVENT_OPEN_TAG.findall(buffer))
            tail = buffer[-overlap:]
    return total


def iter_xes_events(path: Path) -> Iterator[tuple[str | None, int, str | None, ...]]:
    """Yield one tuple per event in file order, shaped like `schema.RAW_COLUMNS`.

    Why events are emitted when their <trace> closes: XES does not require trace attributes
    (including the case id) to precede the trace's events, so a trace's case id is only known for
    certain once the trace is complete. Traces are small (at most 180 events in BPI 2017), so
    buffering one at a time is cheap.

    Why the root is cleared after each trace: ElementTree otherwise keeps every parsed element
    reachable from the root, holding the whole document in memory.
    """
    with _open_binary(path) as handle:
        context = ET.iterparse(handle, events=("start", "end"))
        _, root = next(context)
        for event_type, element in context:
            if event_type != "end" or _local_name(element.tag) != "trace":
                continue

            case_id = None
            event_elements = []
            for child in element:
                name = _local_name(child.tag)
                if name == "event":
                    event_elements.append(child)
                elif name in _ATTRIBUTE_TAGS and child.get("key") == "concept:name":
                    case_id = child.get("value")

            for position, event_element in enumerate(event_elements):
                attributes = {
                    attribute.get("key"): attribute.get("value")
                    for attribute in event_element
                    if _local_name(attribute.tag) in _ATTRIBUTE_TAGS
                }
                yield (
                    case_id,
                    position,
                    attributes.get("concept:name"),
                    attributes.get("lifecycle:transition"),
                    attributes.get("time:timestamp"),
                    attributes.get("org:resource"),
                )
            root.clear()


def parse_xes(path: Path) -> pd.DataFrame:
    """Parse an XES file into the raw events table: every event, every lifecycle transition.

    Why values stay raw strings here: a malformed value (say, an unparseable timestamp) should be
    counted and excluded with a reason during normalization, not crash the parser partway through
    a million-event file.
    """
    return pd.DataFrame(list(iter_xes_events(path)), columns=list(schema.RAW_COLUMNS))
