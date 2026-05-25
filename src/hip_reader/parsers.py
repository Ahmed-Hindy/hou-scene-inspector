"""Small parsers for Houdini .hip archive record payloads."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class NodeInit:
    """Node type information from a ``.init`` record."""

    node_type: str
    matches_definition: bool

    @classmethod
    def parse(cls, text: str) -> "NodeInit":
        """Parse a Houdini ``.init`` record."""

        values: dict[str, str] = {}
        for line in text.splitlines():
            key, separator, value = line.partition(" = ")
            if separator:
                values[key.strip()] = value.strip()
        return cls(
            node_type=values.get("type", ""),
            matches_definition=values.get("matchesdef", "0") == "1",
        )


@dataclass(frozen=True)
class NodeFlags:
    """Common on/off flags parsed from a ``.def`` record."""

    lock: bool = False
    bypass: bool = False
    display: bool = False
    render: bool = False
    template: bool = False
    exposed: bool = False
    raw: str = ""


@dataclass(frozen=True)
class NodeStat:
    """Creation metadata parsed from a ``stat`` block."""

    create: int = 0
    modify: int = 0
    author: str = ""
    access: int = 0


@dataclass(frozen=True)
class NodeInput:
    """One incoming node connection parsed from a ``.def`` inputs block."""

    index: int
    source_node: str
    source_output: int
    connector_id: int
    name: str = ""


@dataclass(frozen=True)
class NodeOutput:
    """One named output connector parsed from a ``.def`` outputs block."""

    index: int
    name: str


@dataclass(frozen=True)
class NodeDef:
    """Network metadata parsed from a Houdini ``.def`` record."""

    comment: str = ""
    position: tuple[float, float] = (0.0, 0.0)
    flags: NodeFlags = field(default_factory=NodeFlags)
    stat: NodeStat = field(default_factory=NodeStat)
    color: tuple[float, float, float] = (0.8, 0.8, 0.8)
    expr_language: str = "hscript"
    inputs: tuple[NodeInput, ...] = ()
    named_inputs: tuple[NodeInput, ...] = ()
    outputs: tuple[NodeOutput, ...] = ()
    raw: str = ""

    @classmethod
    def parse(cls, text: str) -> "NodeDef":
        """Parse the stable, high-value fields from a ``.def`` record."""

        comment = ""
        position = (0.0, 0.0)
        flags = NodeFlags()
        stat = NodeStat()
        color = (0.8, 0.8, 0.8)
        expr_language = "hscript"
        inputs: tuple[NodeInput, ...] = ()
        named_inputs: tuple[NodeInput, ...] = ()
        outputs: tuple[NodeOutput, ...] = ()

        lines = list(text.splitlines())
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if line.startswith("comment "):
                comment = _unquote(line.removeprefix("comment "))
            elif line.startswith("position "):
                parts = line.split()
                if len(parts) >= 3:
                    position = (float(parts[1]), float(parts[2]))
            elif line.startswith("flags ="):
                flags = _parse_flags(line)
            elif line.startswith("stat"):
                stat, index = _parse_stat(lines, index + 1)
            elif line.startswith("inputsNamed3"):
                block, index = _collect_brace_block(lines, index + 1)
                named_inputs = tuple(_parse_input_line(line) for line in block)
                named_inputs = tuple(item for item in named_inputs if item is not None)
            elif line.startswith("inputs"):
                block, index = _collect_brace_block(lines, index + 1)
                inputs = tuple(_parse_input_line(line) for line in block)
                inputs = tuple(item for item in inputs if item is not None)
            elif line.startswith("outputsNamed3"):
                block, index = _collect_brace_block(lines, index + 1)
                outputs = tuple(_parse_output_line(line) for line in block)
                outputs = tuple(item for item in outputs if item is not None)
            elif line.startswith("color UT_Color RGB"):
                parts = line.split()
                if len(parts) >= 6:
                    color = (float(parts[3]), float(parts[4]), float(parts[5]))
            elif line.startswith("exprlanguage "):
                expr_language = line.split(None, 1)[1]
            index += 1

        return cls(
            comment=comment,
            position=position,
            flags=flags,
            stat=stat,
            color=color,
            expr_language=expr_language,
            inputs=inputs,
            named_inputs=named_inputs,
            outputs=outputs,
            raw=text,
        )


@dataclass(frozen=True)
class ChannelReference:
    """Bracketed channel reference embedded in a parameter value."""

    name: str
    value: Any
    raw: str

    @property
    def channel(self) -> str:
        """Return the driven channel name."""

        return self.name

    @property
    def default(self) -> Any:
        """Return the stored fallback value for the channel reference."""

        return self.value


@dataclass(frozen=True)
class ParmValue:
    """One parameter assignment from a ``.parm`` record."""

    name: str
    index: int
    locks: int
    raw_values: tuple[str, ...]

    @property
    def value(self) -> Any:
        """Return a convenient scalar or list representation of the value."""

        values = tuple(_coerce_token(token) for token in self.raw_values)
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return list(values)

    @property
    def is_driven(self) -> bool:
        """Return whether any parameter component is a channel reference."""

        values = self.value
        if isinstance(values, ChannelReference):
            return True
        if isinstance(values, list):
            return any(isinstance(value, ChannelReference) for value in values)
        return False


@dataclass(frozen=True)
class ParmTemplate:
    """A lightweight entry from a ``.spareparmdef`` parameter template block."""

    name: str
    label: str = ""
    baseparm: bool = False
    raw: str = ""


_PARM_HEADER_RE = re.compile(
    r"^(?P<name>\S+)\s+\[\s*(?P<index>\d+)\s+locks=(?P<locks>\d+)\s*\]\s*"
)
_VARIABLE_RE = re.compile(r"^set\s+-g\s+(?P<key>\w+)\s+=\s+'(?P<value>.*)'$")


def parse_parms(text: str) -> dict[str, ParmValue]:
    """Parse a Houdini parameter value table.

    Args:
        text: Payload from a ``.parm`` record.

    Returns:
        Mapping of parameter name to parsed parameter value.
    """

    parms: dict[str, ParmValue] = {}
    for line in text.splitlines():
        parsed = _parse_parm_line(line.strip())
        if parsed is not None:
            parms[parsed.name] = parsed
    return parms


def parse_spareparm_templates(text: str) -> list[ParmTemplate]:
    """Parse lightweight names and labels from a ``.spareparmdef`` record."""

    templates: list[ParmTemplate] = []
    for block in _iter_named_blocks(text, "parm"):
        name = _find_quoted_field(block, "name")
        if not name:
            continue
        templates.append(
            ParmTemplate(
                name=name,
                label=_find_quoted_field(block, "label"),
                baseparm=bool(re.search(r"^\s*baseparm\s*$", block, re.MULTILINE)),
                raw=block,
            )
        )
    return templates


def parse_userdata(data: bytes) -> dict[str, Any]:
    """Parse the observed binary user-data dictionary format.

    The current corpus only proves value type ``3`` as UTF-8 text. Unknown value
    types are preserved with their type tag and raw bytes.
    """

    if len(data) < 4:
        return {}

    result: dict[str, Any] = {}
    offset = 0
    count = struct.unpack_from(">I", data, offset)[0]
    offset += 4

    for _ in range(count):
        if offset + 2 > len(data):
            break
        key_size = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        key = data[offset : offset + key_size].decode("utf-8", errors="replace")
        offset += key_size

        if offset + 6 > len(data):
            break
        value_type = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        value_size = struct.unpack_from(">H", data, offset)[0]
        offset += 2
        value_bytes = data[offset : offset + value_size]
        offset += value_size

        if value_type == 3:
            result[key] = value_bytes.decode("utf-8", errors="replace")
        else:
            result[key] = {"_type": value_type, "_raw": value_bytes}
    return result


def parse_variables(text: str) -> dict[str, str]:
    """Parse global variables from the ``.variables`` record."""

    variables: dict[str, str] = {}
    for line in text.splitlines():
        match = _VARIABLE_RE.match(line.strip())
        if match:
            variables[match.group("key")] = match.group("value")
    return variables


def parse_start(text: str) -> dict[str, Any]:
    """Parse timeline settings from the ``.start`` HScript record."""

    result: dict[str, Any] = {}
    for line in text.splitlines():
        parts = line.strip().split()
        if not parts:
            continue
        if parts[0] == "fps" and len(parts) >= 2:
            result["fps"] = float(parts[1])
        elif parts[0] == "tcur" and len(parts) >= 2:
            result["current_frame"] = float(parts[1])
        elif parts[0] == "frange" and len(parts) >= 3:
            result["frame_range"] = (float(parts[1]), float(parts[2]))
        elif parts[0] == "tset" and len(parts) >= 3:
            result["time_range"] = (float(parts[1]), float(parts[2]))
        elif parts[0] == "unitlength" and len(parts) >= 2:
            result["unit_length"] = float(parts[1])
        elif parts[0] == "unitmass" and len(parts) >= 2:
            result["unit_mass"] = float(parts[1])
        elif parts[0] == "fplayback":
            result["playback_raw"] = line.strip()
    return result


def parse_order(text: str) -> list[str]:
    """Parse a child-order record.

    Houdini stores these as a line count followed by one child name per line.
    If the count is missing or inconsistent, the discovered names are still
    returned because they are the inspectable payload.
    """

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    try:
        int(lines[0])
    except ValueError:
        return lines
    return lines[1:]


def _parse_parm_line(line: str) -> ParmValue | None:
    """Parse one line from a ``.parm`` value table."""

    match = _PARM_HEADER_RE.match(line)
    if not match:
        return None

    value_start = line.find("(", match.end())
    if value_start == -1:
        return None
    value_end = _find_matching_paren(line, value_start)
    if value_end == -1:
        return None

    value_text = line[value_start + 1 : value_end]
    return ParmValue(
        name=match.group("name"),
        index=int(match.group("index")),
        locks=int(match.group("locks")),
        raw_values=tuple(_tokenize_values(value_text)),
    )


def _find_matching_paren(text: str, start: int) -> int:
    """Find a matching ``)`` while respecting quoted strings."""

    depth = 0
    in_quote = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _tokenize_values(text: str) -> list[str]:
    """Tokenize Houdini parm values, preserving quoted and bracketed values."""

    tokens: list[str] = []
    current: list[str] = []
    in_quote = False
    escaped = False
    bracket_depth = 0

    for char in text.strip():
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == '"':
            current.append(char)
            in_quote = not in_quote
            continue
        if not in_quote:
            if char == "[":
                bracket_depth += 1
                current.append(char)
                continue
            if char == "]" and bracket_depth:
                bracket_depth -= 1
                current.append(char)
                continue
            if char.isspace() and bracket_depth == 0:
                if current:
                    tokens.append("".join(current))
                    current = []
                continue
        current.append(char)

    if current:
        tokens.append("".join(current))
    return tokens


def _coerce_token(token: str) -> Any:
    """Coerce a raw token into int, float, string, or channel reference."""

    stripped = token.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return _coerce_channel_reference(stripped)
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1].replace(r"\"", '"')
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        return stripped


def _coerce_channel_reference(token: str) -> ChannelReference:
    """Parse a simple ``[ channel value ]`` parameter token."""

    inner = token[1:-1].strip()
    pieces = inner.split()
    if len(pieces) >= 2:
        return ChannelReference(name=pieces[0], value=_coerce_token(pieces[1]), raw=token)
    return ChannelReference(name=inner, value=None, raw=token)


def _parse_flags(line: str) -> NodeFlags:
    """Parse common on/off tokens from a ``flags =`` line."""

    def enabled(name: str) -> bool:
        match = re.search(rf"\b{re.escape(name)}\s+(on|off)\b", line)
        return bool(match and match.group(1) == "on")

    return NodeFlags(
        lock=enabled("lock"),
        bypass=enabled("bypass"),
        display=enabled("display"),
        render=enabled("render"),
        template=enabled("template"),
        exposed=enabled("exposed"),
        raw=line,
    )


def _parse_stat(lines: list[str], start: int) -> tuple[NodeStat, int]:
    """Parse a ``stat`` block and return the ending line index."""

    create = 0
    modify = 0
    author = ""
    access = 0
    index = start
    while index < len(lines):
        line = lines[index].strip()
        if line == "}":
            break
        key, _, value = line.partition(" ")
        value = value.strip()
        if key == "create":
            create = int(value)
        elif key == "modify":
            modify = int(value)
        elif key == "author":
            author = value
        elif key == "access":
            access = int(value, 8)
        index += 1
    return NodeStat(create=create, modify=modify, author=author, access=access), index


def _collect_brace_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Collect simple one-level brace-block contents from ``.def`` text."""

    index = start
    while index < len(lines) and lines[index].strip() != "{":
        index += 1
    index += 1

    block: list[str] = []
    while index < len(lines):
        line = lines[index].strip()
        if line == "}":
            break
        if line:
            block.append(line)
        index += 1
    return block, index


def _parse_input_line(line: str) -> NodeInput | None:
    """Parse an input connection line from ``inputs`` or ``inputsNamed3``."""

    parts = _split_houdini_tokens(line)
    if len(parts) < 4:
        return None
    try:
        return NodeInput(
            index=int(parts[0]),
            source_node=parts[1],
            source_output=int(parts[2]),
            connector_id=int(parts[3]),
            name=parts[4] if len(parts) > 4 else "",
        )
    except ValueError:
        return None


def _parse_output_line(line: str) -> NodeOutput | None:
    """Parse an output connector line from ``outputsNamed3``."""

    parts = _split_houdini_tokens(line)
    if len(parts) < 2:
        return None
    try:
        return NodeOutput(index=int(parts[0]), name=parts[1])
    except ValueError:
        return None


def _split_houdini_tokens(line: str) -> list[str]:
    """Split a whitespace line while preserving quoted strings as one token."""

    tokens: list[str] = []
    current: list[str] = []
    in_quote = False
    escaped = False

    for char in line.strip():
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if char.isspace() and not in_quote:
            if current:
                tokens.append("".join(current))
                current = []
            continue
        current.append(char)

    if current:
        tokens.append("".join(current))
    return tokens


def _unquote(text: str) -> str:
    """Remove simple surrounding double quotes."""

    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def _iter_named_blocks(text: str, block_name: str) -> Iterable[str]:
    """Yield top-level blocks named ``block_name`` from a brace language."""

    pattern = re.compile(rf"^\s*{re.escape(block_name)}\s*\{{", re.MULTILINE)
    for match in pattern.finditer(text):
        open_brace = text.find("{", match.start())
        close_brace = _find_matching_brace(text, open_brace)
        if close_brace != -1:
            yield text[match.start() : close_brace + 1]


def _find_matching_brace(text: str, start: int) -> int:
    """Find a matching ``}`` while respecting quoted strings."""

    depth = 0
    in_quote = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _find_quoted_field(block: str, field_name: str) -> str:
    """Return a quoted field value from a parameter template block."""

    match = re.search(rf"^\s*{re.escape(field_name)}\s+\"([^\"]*)\"", block, re.MULTILINE)
    return match.group(1) if match else ""
