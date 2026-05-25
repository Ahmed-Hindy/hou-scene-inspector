"""Scene graph assembly for Houdini .hip inspection."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hip_reader.cpio import CpioEntry, read_entries
from hip_reader.jsonutil import json_safe
from hip_reader.parsers import (
    Channel,
    NodeDef,
    NodeInput,
    ParmTemplate,
    ParmValue,
    Take,
    parse_channels,
    parse_parms,
    parse_order,
    parse_spareparm_templates,
    parse_start,
    parse_takes,
    parse_userdata,
    parse_variables,
    NodeInit,
)

NODE_RECORD_EXTENSIONS = {
    ".init",
    ".def",
    ".spareparmdef",
    ".chn",
    ".parm",
    ".userdata",
    ".net",
    ".order",
    ".data",
    ".datablocks",
}

IGNORED_GLOBAL_RECORDS = {
    ".aliases",
    ".application",
    ".contextoptions",
    ".cwd",
    ".hou.session",
    ".OPlibraries",
    ".OPpreferences",
    ".scenefilevisualizers",
    ".styles",
    ".takeconfig",
}


@dataclass
class Connection:
    """Resolved connection between two Houdini nodes."""

    source_path: str
    source_output: int
    destination_path: str
    destination_input: int
    connector_id: int
    name: str = ""
    raw: NodeInput | None = None


@dataclass
class Node:
    """One Houdini operator node discovered in a .hip scene."""

    path: str
    node_type: str = ""
    children: dict[str, "Node"] = field(default_factory=dict)
    parms: dict[str, ParmValue] = field(default_factory=dict)
    definition: NodeDef | None = None
    userdata: dict[str, Any] = field(default_factory=dict)
    channels: dict[str, Channel] = field(default_factory=dict)
    channel_text: str = ""
    spareparm_templates: list[ParmTemplate] = field(default_factory=list)
    net: str = ""
    child_order: list[str] = field(default_factory=list)
    binary_records: dict[str, bytes] = field(default_factory=dict)
    record_names: set[str] = field(default_factory=set)

    @property
    def name(self) -> str:
        """Return the final path component."""

        return posixpath.basename(self.path)

    @property
    def def_(self) -> NodeDef | None:
        """Compatibility alias for ``definition``."""

        return self.definition

    @property
    def inputs(self) -> tuple[NodeInput, ...]:
        """Return raw input metadata parsed from this node's ``.def`` record."""

        return self.definition.inputs if self.definition is not None else ()

    @property
    def outputs(self) -> tuple[Any, ...]:
        """Return raw output metadata parsed from this node's ``.def`` record."""

        return self.definition.outputs if self.definition is not None else ()

    def parm(self, name: str) -> Any:
        """Return a parameter's coerced value, or ``None`` if missing."""

        parm = self.parms.get(name)
        return parm.value if parm is not None else None

    def walk(self) -> list["Node"]:
        """Return this node and all descendants in depth-first order."""

        nodes = [self]
        for child in self.children.values():
            nodes.extend(child.walk())
        return nodes

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly node representation."""

        return {
            "path": self.path,
            "name": self.name,
            "node_type": self.node_type,
            "children": list(self.children),
            "parms": {
                name: {
                    "index": parm.index,
                    "locks": parm.locks,
                    "raw_values": list(parm.raw_values),
                    "value": json_safe(parm.value),
                    "is_driven": parm.is_driven,
                }
                for name, parm in self.parms.items()
            },
            "definition": json_safe(self.definition),
            "userdata": json_safe(self.userdata),
            "channels": json_safe(self.channels),
            "spareparm_templates": json_safe(self.spareparm_templates),
            "net": self.net,
            "child_order": self.child_order,
            "binary_records": {
                key: {"size": len(value)} for key, value in self.binary_records.items()
            },
            "record_names": sorted(self.record_names),
        }


@dataclass
class HipFile:
    """Inspectable representation of a Houdini .hip scene."""

    path: Path
    records: list[CpioEntry] = field(default_factory=list)
    variables: dict[str, str] = field(default_factory=dict)
    start: dict[str, Any] = field(default_factory=dict)
    takes: list[Take] = field(default_factory=list)
    take_text: str = ""
    networks: dict[str, dict[str, Node]] = field(default_factory=dict)
    context_nodes: dict[str, Node] = field(default_factory=dict)
    unparsed_records: dict[str, CpioEntry] = field(default_factory=dict)

    @property
    def houdini_version(self) -> str:
        """Return the Houdini version recorded when the file was saved."""

        return self.variables.get("_HIP_SAVEVERSION", "")

    @property
    def save_platform(self) -> str:
        """Return the Houdini save platform string."""

        return self.variables.get("_HIP_SAVEPLATFORM", "")

    @property
    def save_time(self) -> str:
        """Return the Houdini save time string."""

        return self.variables.get("_HIP_SAVETIME", "")

    @property
    def fps(self) -> float:
        """Return the scene FPS, defaulting to Houdini's common default."""

        return self.start.get("fps", 24.0)

    @property
    def current_frame(self) -> float:
        """Return the current frame recorded in the file."""

        return self.start.get("current_frame", 1.0)

    @property
    def frame_range(self) -> tuple[float, float]:
        """Return the playback frame range."""

        return self.start.get("frame_range", (1.0, 240.0))

    @property
    def time_range(self) -> tuple[float, float]:
        """Return the playback time range."""

        return self.start.get("time_range", (0.0, 10.0))

    @property
    def active_take(self) -> str:
        """Return the active take recorded in global variables."""

        return self.variables.get("ACTIVETAKE", "")

    @classmethod
    def load(cls, path: str | Path) -> "HipFile":
        """Load and inspect a Houdini .hip file without importing Houdini."""

        hip_path = Path(path)
        hip = cls(path=hip_path, records=list(read_entries(hip_path)))
        raw_nodes: dict[str, dict[str, CpioEntry]] = {}

        for entry in hip.records:
            if entry.name == ".start":
                hip.start = parse_start(entry.text())
            elif entry.name == ".variables":
                hip.variables = parse_variables(entry.text())
            elif entry.name == ".takes":
                hip.take_text = entry.text()
                hip.takes = parse_takes(hip.take_text)
            elif entry.name in IGNORED_GLOBAL_RECORDS:
                hip.unparsed_records[entry.name] = entry
            else:
                base, extension = split_record_extension(entry.name)
                if extension in NODE_RECORD_EXTENSIONS:
                    raw_nodes.setdefault(base, {})[extension] = entry
                else:
                    hip.unparsed_records[entry.name] = entry

        hip._build_graph(raw_nodes)
        return hip

    def node(self, path: str) -> Node | None:
        """Return a node by absolute Houdini path, such as ``/obj/geo1``."""

        parts = path.strip("/").split("/")
        if len(parts) < 2:
            return self.context_nodes.get(parts[0]) if parts and parts[0] else None

        current = self.networks.get(parts[0], {}).get(parts[1])
        for part in parts[2:]:
            if current is None:
                return None
            current = current.children.get(part)
        return current

    def all_nodes(self) -> list[Node]:
        """Return all non-context nodes in the scene."""

        nodes: list[Node] = []
        for context_nodes in self.networks.values():
            for node in context_nodes.values():
                nodes.extend(node.walk())
        return nodes

    def connections(self) -> list[Connection]:
        """Return resolved node graph connections."""

        connections: list[Connection] = []
        node_paths = {node.path for node in self.all_nodes()}
        for node in self.all_nodes():
            if node.definition is None:
                continue
            named_inputs = {
                connection.index: connection for connection in node.definition.named_inputs
            }
            parent_path = posixpath.dirname(node.path)
            for raw_input in node.definition.inputs:
                source_path = posixpath.join(parent_path, raw_input.source_node)
                if not source_path.startswith("/"):
                    source_path = "/" + source_path
                name = raw_input.name or named_inputs.get(raw_input.index, raw_input).name
                if source_path not in node_paths:
                    source_path = raw_input.source_node
                connections.append(
                    Connection(
                        source_path=source_path,
                        source_output=raw_input.source_output,
                        destination_path=node.path,
                        destination_input=raw_input.index,
                        connector_id=raw_input.connector_id,
                        name=name,
                        raw=raw_input,
                    )
                )
        return connections

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly scene representation."""

        return {
            "path": str(self.path),
            "houdini_version": self.houdini_version,
            "save_platform": self.save_platform,
            "save_time": self.save_time,
            "fps": self.fps,
            "current_frame": self.current_frame,
            "frame_range": self.frame_range,
            "time_range": self.time_range,
            "active_take": self.active_take,
            "variables": self.variables,
            "records": len(self.records),
            "nodes": [node.to_dict() for node in self.all_nodes()],
            "connections": json_safe(self.connections()),
            "takes": json_safe(self.takes),
            "unparsed_records": sorted(self.unparsed_records),
        }

    def _build_graph(self, raw_nodes: dict[str, dict[str, CpioEntry]]) -> None:
        """Build parent/child node relationships from archive record paths."""

        nodes: dict[str, Node] = {}

        for base_path, records in raw_nodes.items():
            op_path = "/" + base_path
            node = nodes.setdefault(op_path, Node(path=op_path))
            node.record_names.update(entry.name for entry in records.values())

            if ".init" in records:
                init = NodeInit.parse(records[".init"].text())
                node.node_type = init.node_type
            if ".def" in records:
                node.definition = NodeDef.parse(records[".def"].text())
            if ".parm" in records:
                node.parms = parse_parms(records[".parm"].text())
            if ".userdata" in records:
                node.userdata = parse_userdata(records[".userdata"].content)
            if ".chn" in records:
                node.channel_text = records[".chn"].text()
                node.channels = parse_channels(node.channel_text)
            if ".spareparmdef" in records:
                node.spareparm_templates = parse_spareparm_templates(
                    records[".spareparmdef"].text()
                )
            if ".net" in records:
                node.net = records[".net"].text()
            if ".order" in records:
                node.child_order = parse_order(records[".order"].text())
            if ".data" in records:
                node.binary_records["data"] = records[".data"].content
            if ".datablocks" in records:
                node.binary_records["datablocks"] = records[".datablocks"].content

        for op_path, node in nodes.items():
            parent_path = posixpath.dirname(op_path)
            if parent_path in nodes and parent_path != op_path:
                nodes[parent_path].children[node.name] = node

        for op_path, node in nodes.items():
            parts = op_path.strip("/").split("/")
            if len(parts) == 1:
                self.context_nodes[parts[0]] = node
                self.networks.setdefault(parts[0], {})
            elif len(parts) == 2:
                self.networks.setdefault(parts[0], {})[parts[1]] = node

    def __repr__(self) -> str:
        """Return a concise debug representation."""

        return (
            f"HipFile(version={self.houdini_version!r}, fps={self.fps}, "
            f"frame_range={self.frame_range}, nodes={len(self.all_nodes())})"
        )


def split_record_extension(name: str) -> tuple[str, str]:
    """Split a Houdini archive record into base path and semantic extension."""

    dot = name.rfind(".")
    if dot == -1:
        return name, ""
    return name[:dot], name[dot:]
