"""Command-line interface for inspecting Houdini .hip files."""

from __future__ import annotations

import argparse
from pathlib import Path

from hip_reader.cpio import read_entries
from hip_reader.scene import HipFile, Node


def main() -> None:
    """Run the ``hip-inspect`` command."""

    parser = argparse.ArgumentParser(description="Inspect Houdini .hip files")
    subparsers = parser.add_subparsers(dest="command")

    records_parser = subparsers.add_parser("records", help="List CPIO records")
    records_parser.add_argument("hip_file", type=Path)

    summary_parser = subparsers.add_parser("summary", help="Print scene summary")
    summary_parser.add_argument("hip_file", type=Path)

    tree_parser = subparsers.add_parser("tree", help="Print node tree")
    tree_parser.add_argument("hip_file", type=Path)

    args = parser.parse_args()
    if args.command == "records":
        _print_records(args.hip_file)
    elif args.command == "tree":
        _print_tree(HipFile.load(args.hip_file))
    else:
        hip_file = getattr(args, "hip_file", None)
        if hip_file is None:
            parser.print_help()
            return
        _print_summary(HipFile.load(hip_file))


def _print_records(path: Path) -> None:
    """Print archive records with offsets and sizes."""

    for entry in read_entries(path):
        print(f"{entry.header_offset:08x} {entry.size:8d} {entry.name}")


def _print_summary(hip: HipFile) -> None:
    """Print high-level scene metadata."""

    print(f"path: {hip.path}")
    print(f"houdini_version: {hip.houdini_version}")
    print(f"save_platform: {hip.save_platform}")
    print(f"save_time: {hip.save_time}")
    print(f"fps: {hip.fps:g}")
    print(f"frame_range: {hip.frame_range[0]:g}-{hip.frame_range[1]:g}")
    print(f"records: {len(hip.records)}")
    print(f"nodes: {len(hip.all_nodes())}")
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


def _print_tree(hip: HipFile) -> None:
    """Print node hierarchy."""

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
