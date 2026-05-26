"""Export a conservative Houdini oracle snapshot for a .hip file.

Run this script with Houdini's ``hython``. It may import ``hou`` and inspect the
scene through Houdini APIs, but it must not be imported by the runtime package.
The exported JSON is intentionally structural: it avoids cooking geometry and
does not evaluate node networks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import hou


def main() -> None:
    """Export a Houdini-derived oracle JSON document."""

    parser = argparse.ArgumentParser(description="Export a Houdini oracle snapshot")
    parser.add_argument("hip_file", type=Path)
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    payload = export_oracle(args.hip_file)
    text = json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def export_oracle(path: Path) -> dict[str, Any]:
    """Load ``path`` in Houdini and return a structural oracle snapshot."""

    hip_path = path.resolve()
    hou.hipFile.load(str(hip_path), suppress_save_prompt=True)
    nodes = [_node_payload(node) for node in _iter_scene_nodes()]
    connections = [
        connection
        for node in nodes
        for connection in node["connections"]
    ]
    return {
        "schema_version": 1,
        "source": "houdini-hython",
        "hip_file": str(hip_path),
        "houdini_version": hou.applicationVersionString(),
        "nodes": nodes,
        "connections": connections,
        "takes": [_take_payload(take) for take in hou.takes.takes()],
    }


def _iter_scene_nodes() -> list[hou.Node]:
    """Return non-context nodes in deterministic path order."""

    nodes: list[hou.Node] = []
    for context in sorted(hou.node("/").children(), key=lambda node: node.path()):
        nodes.extend(_walk_children(context))
    return sorted(nodes, key=lambda node: node.path())


def _walk_children(node: hou.Node) -> list[hou.Node]:
    """Return child nodes recursively, excluding the supplied container."""

    nodes: list[hou.Node] = []
    for child in sorted(node.children(), key=lambda item: item.path()):
        nodes.append(child)
        nodes.extend(_walk_children(child))
    return nodes


def _node_payload(node: hou.Node) -> dict[str, Any]:
    """Return a structural snapshot for one Houdini node."""

    definition = node.type().definition()
    return {
        "path": node.path(),
        "name": node.name(),
        "node_type": node.type().name(),
        "parent_path": node.parent().path() if node.parent() else "",
        "children": [child.path() for child in sorted(node.children(), key=lambda item: item.path())],
        "position": _position(node),
        "flags": _flag_payload(node),
        "type_definition": {
            "has_definition": definition is not None,
            "library_file_path": definition.libraryFilePath() if definition else "",
            "node_type_name": definition.nodeTypeName() if definition else "",
        },
        "parms": _parm_payloads(node),
        "channels": _channel_payloads(node),
        "connections": _connection_payloads(node),
        "userdata": node.userDataDict(),
    }


def _position(node: hou.Node) -> list[float]:
    """Return the network editor position for a node."""

    position = node.position()
    return [position.x(), position.y()]


def _flag_payload(node: hou.Node) -> dict[str, bool]:
    """Return common node flags when supported by the node type."""

    return {
        "bypass": _call_bool(node, "isBypassed"),
        "display": _call_bool(node, "isDisplayFlagSet"),
        "render": _call_bool(node, "isRenderFlagSet"),
        "template": _call_bool(node, "isTemplateFlagSet"),
        "hard_locked": _call_bool(node, "isHardLocked"),
    }


def _call_bool(node: hou.Node, method_name: str) -> bool:
    """Call a node flag method when it exists and return ``False`` otherwise."""

    method = getattr(node, method_name, None)
    if method is None:
        return False
    try:
        return bool(method())
    except hou.Error:
        return False


def _parm_payloads(node: hou.Node) -> dict[str, dict[str, Any]]:
    """Return raw parameter tuple values without evaluating expressions."""

    parms: dict[str, dict[str, Any]] = {}
    for parm_tuple in sorted(node.parmTuples(), key=lambda item: item.name()):
        raw_values: list[str] = []
        component_names: list[str] = []
        for parm in parm_tuple:
            component_names.append(parm.name())
            try:
                raw_values.append(parm.rawValue())
            except hou.Error:
                raw_values.append("")
        parms[parm_tuple.name()] = {
            "component_names": component_names,
            "raw_values": raw_values,
        }
    return parms


def _channel_payloads(node: hou.Node) -> dict[str, dict[str, Any]]:
    """Return keyframe/expression channel metadata without evaluating channels."""

    channels: dict[str, dict[str, Any]] = {}
    for parm_tuple in sorted(node.parmTuples(), key=lambda item: item.name()):
        for parm in parm_tuple:
            keyframes = _keyframe_payloads(parm)
            expression = _parm_expression(parm)
            if keyframes or expression:
                channels[parm.name()] = {
                    "parm_tuple": parm_tuple.name(),
                    "raw_value": _safe_raw_value(parm),
                    "expression": expression,
                    "keyframes": keyframes,
                }
    return channels


def _safe_raw_value(parm: hou.Parm) -> str:
    """Return ``parm.rawValue()`` while tolerating unsupported parm types."""

    try:
        return parm.rawValue()
    except hou.Error:
        return ""


def _parm_expression(parm: hou.Parm) -> str:
    """Return a parm expression string when one exists."""

    try:
        return parm.expression()
    except hou.Error:
        return ""


def _keyframe_payloads(parm: hou.Parm) -> list[dict[str, Any]]:
    """Return keyframe metadata without evaluating the parameter."""

    keyframes = []
    try:
        parm_keyframes = parm.keyframes()
    except hou.Error:
        return keyframes
    for keyframe in parm_keyframes:
        expression = ""
        try:
            expression = keyframe.expression()
        except hou.Error:
            pass
        keyframes.append(
            {
                "frame": keyframe.frame(),
                "value": keyframe.value(),
                "expression": expression,
            }
        )
    return keyframes


def _connection_payloads(node: hou.Node) -> list[dict[str, Any]]:
    """Return incoming connection metadata for a node."""

    connections = []
    for connection in node.inputConnections():
        input_node = connection.inputNode()
        output_node = connection.outputNode()
        if input_node is None or output_node is None:
            continue
        connections.append(
            {
                "source_path": input_node.path(),
                "source_output": connection.outputIndex(),
                "destination_path": output_node.path(),
                "destination_input": connection.inputIndex(),
                "source_output_name": connection.inputName(),
                "destination_input_name": connection.outputName(),
            }
        )
    return sorted(
        connections,
        key=lambda item: (
            item["destination_path"],
            item["destination_input"],
            item["source_path"],
        ),
    )


def _take_payload(take: hou.Take) -> dict[str, Any]:
    """Return simple take hierarchy metadata."""

    parent = take.parent()
    return {
        "name": take.name(),
        "parent": parent.name() if parent is not None else "",
        "children": [child.name() for child in take.children()],
    }


if __name__ == "__main__":
    main()
