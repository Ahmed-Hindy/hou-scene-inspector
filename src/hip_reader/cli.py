"""Command-line interface for inspecting Houdini .hip files."""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from hip_reader.cpio import read_entries
from hip_reader.jsonutil import json_safe
from hip_reader.scene import HipFile, Node


def main() -> None:
    """Run the ``hip-inspect`` command."""

    parser = argparse.ArgumentParser(description="Inspect Houdini .hip files")
    subparsers = parser.add_subparsers(dest="command")

    records_parser = subparsers.add_parser("records", help="List CPIO records")
    records_parser.add_argument("--json", action="store_true", help="Output JSON")
    records_parser.add_argument("hip_file", type=Path)

    summary_parser = subparsers.add_parser("summary", help="Print scene summary")
    summary_parser.add_argument("--json", action="store_true", help="Output JSON")
    summary_parser.add_argument("hip_file", type=Path)

    tree_parser = subparsers.add_parser("tree", help="Print node tree")
    tree_parser.add_argument("--json", action="store_true", help="Output JSON")
    tree_parser.add_argument("hip_file", type=Path)

    node_parser = subparsers.add_parser("node", help="Print one node")
    node_parser.add_argument("--json", action="store_true", help="Output JSON")
    node_parser.add_argument("hip_file", type=Path)
    node_parser.add_argument("node_path")

    dump_parser = subparsers.add_parser("dump-record", help="Dump one CPIO record")
    dump_parser.add_argument("--json", action="store_true", help="Output JSON")
    dump_parser.add_argument("hip_file", type=Path)
    dump_parser.add_argument("record_name")

    args = parser.parse_args()
    if args.command == "records":
        _print_records(args.hip_file, as_json=args.json)
    elif args.command == "tree":
        _print_tree(HipFile.load(args.hip_file), as_json=args.json)
    elif args.command == "node":
        _print_node_detail(HipFile.load(args.hip_file), args.node_path, as_json=args.json)
    elif args.command == "dump-record":
        _dump_record(args.hip_file, args.record_name, as_json=args.json)
    else:
        hip_file = getattr(args, "hip_file", None)
        if hip_file is None:
            parser.print_help()
            return
        _print_summary(HipFile.load(hip_file), as_json=args.json)


def _print_records(path: Path, *, as_json: bool = False) -> None:
    """Print archive records with offsets and sizes."""

    records = [
        {
            "name": entry.name,
            "size": entry.size,
            "mode": entry.mode,
            "mtime": entry.mtime,
            "header_offset": entry.header_offset,
            "data_offset": entry.data_offset,
            "classification": entry.classification,
        }
        for entry in read_entries(path)
    ]
    if as_json:
        _print_json(records)
        return
    for record in records:
        print(f"{record['header_offset']:08x} {record['size']:8d} {record['name']}")


def _print_summary(hip: HipFile, *, as_json: bool = False) -> None:
    """Print high-level scene metadata."""

    if as_json:
        _print_json(hip.to_dict())
        return

    print(f"path: {hip.path}")
    print(f"houdini_version: {hip.houdini_version}")
    print(f"save_platform: {hip.save_platform}")
    print(f"save_time: {hip.save_time}")
    print(f"fps: {hip.fps:g}")
    print(f"frame_range: {hip.frame_range[0]:g}-{hip.frame_range[1]:g}")
    print(f"records: {len(hip.records)}")
    print(f"nodes: {len(hip.all_nodes())}")
    if hip.takes:
        print(f"takes: {', '.join(take.name for take in hip.takes)}")
    for node in hip.all_nodes():
        position = node.definition.position if node.definition else None
        inputs = ""
        if node.definition and node.definition.inputs:
            input_parts = [
                f"{connection.index}:{connection.source_node}[{connection.source_output}]"
                for connection in node.definition.inputs
            ]
            inputs = f" inputs={','.join(input_parts)}"
        print(
            f"  {node.path} type={node.node_type or '?'} "
            f"position={position}{inputs}"
        )
    for connection in hip.connections():
        print(
            "  edge "
            f"{connection.source_path}[{connection.source_output}] -> "
            f"{connection.destination_path}[{connection.destination_input}]"
        )


def _print_tree(hip: HipFile, *, as_json: bool = False) -> None:
    """Print node hierarchy."""

    if as_json:
        _print_json(
            {
                context: [_node_tree_dict(node) for node in nodes.values()]
                for context, nodes in hip.networks.items()
            }
        )
        return

    for context, context_node in sorted(hip.context_nodes.items()):
        print(f"/{context}")
        for node in hip.networks.get(context, {}).values():
            _print_node(node, level=1)
            if context_node.net.strip() and context_node.net.strip() != "1":
                print(f"  net: {context_node.net.strip()}")


def _print_node(node: Node, level: int) -> None:
    """Print a node and its descendants."""

    indent = "  " * level
    suffix = f" [{node.node_type}]" if node.node_type else ""
    print(f"{indent}{node.name}{suffix}")
    for child in node.children.values():
        _print_node(child, level + 1)


def _print_node_detail(hip: HipFile, node_path: str, *, as_json: bool = False) -> None:
    """Print one node by path."""

    node = hip.node(node_path)
    if node is None:
        raise SystemExit(f"Node not found: {node_path}")
    if as_json:
        _print_json(node.to_dict())
        return
    print(f"path: {node.path}")
    print(f"type: {node.node_type}")
    if node.definition:
        print(f"position: {node.definition.position}")
        print(f"flags: {node.definition.flags}")
    if node.parms:
        print("parms:")
        for name, parm in node.parms.items():
            print(f"  {name}: {parm.value!r}")
    if node.channels:
        print("channels:")
        for name in node.channels:
            print(f"  {name}")


def _dump_record(path: Path, record_name: str, *, as_json: bool = False) -> None:
    """Dump one archive record."""

    for entry in read_entries(path):
        if entry.name != record_name:
            continue
        if as_json:
            _print_json(
                {
                    "name": entry.name,
                    "size": entry.size,
                    "classification": entry.classification,
                    "text": entry.text() if entry.classification != "binary" else None,
                    "content": {
                        "encoding": "base64",
                        "data": base64.b64encode(entry.content).decode("ascii"),
                    },
                }
            )
            return
        if entry.classification == "binary":
            print(entry.content.hex(" "))
        else:
            print(entry.text(), end="")
        return
    raise SystemExit(f"Record not found: {record_name}")


def _node_tree_dict(node: Node) -> dict[str, object]:
    """Return a compact JSON tree node."""

    return {
        "path": node.path,
        "name": node.name,
        "node_type": node.node_type,
        "children": [_node_tree_dict(child) for child in node.children.values()],
    }


def _print_json(value: object) -> None:
    """Print a JSON document."""

    print(json.dumps(json_safe(value), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
