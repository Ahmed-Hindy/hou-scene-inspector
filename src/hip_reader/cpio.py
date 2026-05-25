"""Reader for Houdini .hip files stored as old portable CPIO archives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

CPIO_MAGIC = b"070707"
HEADER_SIZE = 76
TRAILER_NAME = "TRAILER!!!"


@dataclass(frozen=True)
class CpioEntry:
    """One named record from a Houdini .hip CPIO stream.

    Attributes:
        name: Archive record name, such as ``obj/geo1.parm``.
        content: Raw record payload bytes.
        mode: CPIO mode field parsed from octal.
        mtime: CPIO modification timestamp field parsed from octal.
        header_offset: Byte offset where the CPIO header starts.
        data_offset: Byte offset where the payload starts.
    """

    name: str
    content: bytes
    mode: int
    mtime: int
    header_offset: int
    data_offset: int

    @property
    def size(self) -> int:
        """Return the payload size in bytes."""
        return len(self.content)

    def text(self, encoding: str = "utf-8") -> str:
        """Decode the payload as text, replacing invalid characters."""
        return self.content.decode(encoding, errors="replace")

    def is_text(self, encoding: str = "utf-8") -> bool:
        """Return whether the payload decodes cleanly as text."""
        try:
            self.content.decode(encoding)
        except UnicodeDecodeError:
            return False
        return True


class CpioFormatError(ValueError):
    """Raised when a file is not a valid old portable CPIO stream."""


def read_entries(path: str | Path) -> Iterator[CpioEntry]:
    """Yield CPIO records from a Houdini .hip file.

    Args:
        path: Path to a ``.hip`` file.

    Yields:
        Entries in archive order, excluding the ``TRAILER!!!`` record.

    Raises:
        CpioFormatError: If the stream has invalid magic, octal fields, or a
            truncated record.
    """

    with Path(path).open("rb") as stream:
        yield from read_entries_from_stream(stream)


def read_entries_from_stream(stream: BinaryIO) -> Iterator[CpioEntry]:
    """Yield entries from an already-open old portable CPIO stream."""

    first_magic = stream.read(len(CPIO_MAGIC))
    if first_magic != CPIO_MAGIC:
        raise CpioFormatError(
            f"Expected old portable CPIO magic {CPIO_MAGIC!r}, got {first_magic!r}"
        )
    stream.seek(0)

    while True:
        header_offset = stream.tell()
        header = stream.read(HEADER_SIZE)
        if not header:
            return
        if len(header) != HEADER_SIZE:
            raise CpioFormatError(f"Truncated CPIO header at offset {header_offset}")
        if header[:6] != CPIO_MAGIC:
            raise CpioFormatError(f"Invalid CPIO magic at offset {header_offset}")

        mode = _read_octal(header[18:24], "mode", header_offset)
        mtime = _read_octal(header[48:59], "mtime", header_offset)
        name_size = _read_octal(header[59:65], "namesize", header_offset)
        file_size = _read_octal(header[65:76], "filesize", header_offset)

        name_bytes = stream.read(name_size)
        if len(name_bytes) != name_size:
            raise CpioFormatError(f"Truncated CPIO name at offset {stream.tell()}")
        name = name_bytes.rstrip(b"\0").decode("utf-8", errors="replace")

        data_offset = stream.tell()
        content = stream.read(file_size)
        if len(content) != file_size:
            raise CpioFormatError(f"Truncated CPIO payload for {name!r}")

        if name == TRAILER_NAME:
            return

        yield CpioEntry(
            name=name,
            content=content,
            mode=mode,
            mtime=mtime,
            header_offset=header_offset,
            data_offset=data_offset,
        )


def _read_octal(raw: bytes, field_name: str, offset: int) -> int:
    """Parse an ASCII octal CPIO header field."""

    try:
        return int(raw, 8)
    except ValueError as exc:
        value = raw.decode("ascii", errors="replace")
        raise CpioFormatError(
            f"Invalid octal {field_name} field {value!r} at offset {offset}"
        ) from exc
