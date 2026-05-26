"""Command-line interface for inspecting Houdini .hip files."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from hip_reader.cpio import CpioEntry, read_entries
from hip_reader.jsonutil import json_safe
from hip_reader.oracle import compare_oracle, load_oracle
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

    spare_parser = subparsers.add_parser("spare-parms", help="List spare parm templates")
    spare_parser.add_argument("--json", action="store_true", help="Output JSON")
    spare_parser.add_argument("hip_file", type=Path)
    spare_parser.add_argument("node_path")

    binary_parser = subparsers.add_parser("binary-records", help="List binary records")
    binary_parser.add_argument("--json", action="store_true", help="Output JSON")
    binary_parser.add_argument("hip_file", type=Path)
    binary_parser.add_argument("node_path", nargs="?")

    channels_parser = subparsers.add_parser("channels", help="List channels")
    channels_parser.add_argument("--json", action="store_true", help="Output JSON")
    channels_parser.add_argument("hip_file", type=Path)

    takes_parser = subparsers.add_parser("takes", help="List takes")
    takes_parser.add_argument("--json", action="store_true", help="Output JSON")
    takes_parser.add_argument("hip_file", type=Path)

    dump_parser = subparsers.add_parser("dump-record", help="Dump one CPIO record")
    dump_parser.add_argument("--json", action="store_true", help="Output JSON")
    dump_parser.add_argument("hip_file", type=Path)
    dump_parser.add_argument("record_name")

    diff_parser = subparsers.add_parser("diff-records", help="Diff archive records")
    diff_parser.add_argument("--json", action="store_true", help="Output JSON")
    diff_parser.add_argument("left", type=Path)
    diff_parser.add_argument("right", type=Path)

    oracle_parser = subparsers.add_parser(
        "compare-oracle",
        help="Compare against a Houdini oracle JSON snapshot",
    )
    oracle_parser.add_argument("--json", action="store_true", help="Output JSON")
    oracle_parser.add_argument("hip_file", type=Path)
    oracle_parser.add_argument("oracle_json", type=Path)

    args = parser.parse_args()
    if args.command == "records":
        _print_records(args.hip_file, as_json=args.json)
    elif args.command == "tree":
        _print_tree(HipFile.load(args.hip_file), as_json=args.json)
    elif args.command == "node":
        _print_node_detail(HipFile.load(args.hip_file), args.node_path, as_json=args.json)
    elif args.command == "spare-parms":
        _print_spare_parms(HipFile.load(args.hip_file), args.node_path, as_json=args.json)
    elif args.command == "binary-records":
        _print_binary_records(
            HipFile.load(args.hip_file),
            node_path=args.node_path,
            as_json=args.json,
        )
    elif args.command == "channels":
        _print_channels(HipFile.load(args.hip_file), as_json=args.json)
    elif args.command == "takes":
        _print_takes(HipFile.load(args.hip_file), as_json=args.json)
    elif args.command == "dump-record":
        _dump_record(args.hip_file, args.record_name, as_json=args.json)
    elif args.command == "diff-records":
        _diff_records(args.left, args.right, as_json=args.json)
    elif args.command == "compare-oracle":
        _compare_oracle(args.hip_file, args.oracle_json, as_json=args.json)
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
        for name, channel in node.channels.items():
            labels = []
            if channel.is_keyframed:
                labels.append("keyframed")
            if channel.is_expression:
                labels.append("expression")
            suffix = f" ({', '.join(labels)})" if labels else ""
            print(f"  {name}: {len(channel.segments)} segment(s){suffix}")
    links = node.driven_parm_links()
    if links:
        print("driven parms:")
        for link in links:
            resolved = "resolved" if link.is_resolved else "unresolved"
            print(
                f"  {link.parm_name}[{link.component_index}] -> "
                f"{link.channel_name} ({resolved})"
            )


def _print_spare_parms(hip: HipFile, node_path: str, *, as_json: bool = False) -> None:
    """Print spare parameter templates for one node."""

    node = hip.node(node_path)
    if node is None:
        raise SystemExit(f"Node not found: {node_path}")
    if as_json:
        _print_json(node.spareparm_templates)
        return
    if not node.spareparm_templates:
        print(f"No spare parm templates found on {node.path}")
        return
    for template in node.spareparm_templates:
        flags = []
        if template.baseparm:
            flags.append("base")
        if template.invisible:
            flags.append("invisible")
        if template.join_next:
            flags.append("join-next")
        if template.no_label:
            flags.append("no-label")
        suffix = f" [{' '.join(flags)}]" if flags else ""
        type_name = template.type_name or "baseparm"
        print(
            f"{template.name}: {type_name} "
            f"label={template.label!r} folder={template.folder_label!r}{suffix}"
        )
        if template.default:
            print(f"  default={list(template.default)!r}")
        if template.range:
            print(f"  range={list(template.range)!r}")
        if template.menu:
            print(f"  menu={list(template.menu)!r}")
        if template.disable_when:
            print(f"  disablewhen={template.disable_when!r}")
        if template.hide_when:
            print(f"  hidewhen={template.hide_when!r}")


def _print_binary_records(
    hip: HipFile,
    *,
    node_path: str | None = None,
    as_json: bool = False,
) -> None:
    """Print metadata-only summaries for binary node records."""

    if node_path:
        node = hip.node(node_path)
        if node is None:
            raise SystemExit(f"Node not found: {node_path}")
        records = node.binary_record_infos()
    else:
        records = hip.binary_record_summary()
    if as_json:
        _print_json(records)
        return
    if not records:
        target = node_path or str(hip.path)
        print(f"No binary records found for {target}")
        return
    for record in records:
        print(
            f"{record.node_path} {record.semantic_name}: "
            f"{record.size} bytes {record.classification} "
            f"sha256={record.sha256}"
        )
        print(f"  record={record.record_name}")
        print(f"  preview[{record.preview_size}]={record.preview_hex}")


def _print_channels(hip: HipFile, *, as_json: bool = False) -> None:
    """Print channel and driven-parameter information."""

    rows = hip.channel_summary()
    if as_json:
        _print_json(rows)
        return
    if not rows:
        print("No channels found")
        return
    for row in rows:
        labels = []
        if row["is_keyframed"]:
            labels.append("keyframed")
        if row["is_expression"]:
            labels.append("expression")
        suffix = f" ({', '.join(labels)})" if labels else ""
        print(
            f"{row['node_path']} {row['channel_name']}: "
            f"{row['segments']} segment(s){suffix}"
        )
        for link in row["driven_parms"]:
            print(
                f"  drives {link['parm_name']}[{link['component_index']}] "
                f"default={link['default']!r}"
            )


def _print_takes(hip: HipFile, *, as_json: bool = False) -> None:
    """Print take hierarchy and observed parameter overrides."""

    if as_json:
        _print_json(hip.takes)
        return
    if not hip.takes:
        print("No takes found")
        return
    for take in hip.takes:
        print(f"{take.name} children={take.child_count}")
        for override in take.overrides:
            print(f"  override {override.path} {override.parm}")
            for parm_name, parm in override.parms.items():
                print(f"    {parm_name}: {parm.value!r}")


def _dump_record(path: Path, record_name: str, *, as_json: bool = False) -> None:
    """Dump one archive record."""

    for entry in read_entries(path):
        if entry.name != record_name:
            continue
        if as_json:
            is_text = entry.classification in {"text", "structured-text"}
            _print_json(
                {
                    "name": entry.name,
                    "size": entry.size,
                    "classification": entry.classification,
                    "text": entry.text() if is_text else None,
                    "content": {
                        "encoding": "base64",
                        "data": base64.b64encode(entry.content).decode("ascii"),
                    },
                }
            )
            return
        if entry.classification not in {"text", "structured-text"}:
            print(entry.content.hex(" "))
        else:
            print(entry.text(), end="")
        return
    raise SystemExit(f"Record not found: {record_name}")


def _diff_records(left: Path, right: Path, *, as_json: bool = False) -> None:
    """Print a record-level diff between two CPIO archives."""

    payload = _record_diff(left, right)
    if as_json:
        _print_json(payload)
        return
    for name in payload["removed"]:
        print(f"removed {name}")
    for name in payload["added"]:
        print(f"added {name}")
    for item in payload["changed"]:
        print(
            f"changed {item['name']} "
            f"{item['left_size']} -> {item['right_size']} bytes"
        )
    print(f"unchanged {payload['unchanged_count']}")


def _compare_oracle(hip_file: Path, oracle_json: Path, *, as_json: bool = False) -> None:
    """Compare hip-reader output with a Houdini oracle snapshot."""

    payload = compare_oracle(HipFile.load(hip_file), load_oracle(oracle_json))
    if as_json:
        _print_json(payload)
        return
    status = "OK" if payload["ok"] else "MISMATCH"
    print(f"{status}: {payload['mismatch_count']} mismatch(es)")
    for key, value in payload["summary"].items():
        print(f"{key}: {value}")
    for mismatch in payload["mismatches"]:
        print(f"{mismatch['kind']} {mismatch['path']}")
        print(f"  hip_reader: {mismatch['hip_reader']!r}")
        print(f"  oracle:     {mismatch['oracle']!r}")


def _record_diff(left: Path, right: Path) -> dict[str, object]:
    """Return a scriptable record diff payload."""

    left_records = {entry.name: entry for entry in read_entries(left)}
    right_records = {entry.name: entry for entry in read_entries(right)}
    left_names = set(left_records)
    right_names = set(right_records)
    changed = []
    unchanged = 0
    for name in sorted(left_names & right_names):
        left_entry = left_records[name]
        right_entry = right_records[name]
        if _entry_digest(left_entry) == _entry_digest(right_entry):
            unchanged += 1
            continue
        changed.append(
            {
                "name": name,
                "left_size": left_entry.size,
                "right_size": right_entry.size,
                "left_hash": _entry_hash(left_entry),
                "right_hash": _entry_hash(right_entry),
                "left_classification": left_entry.classification,
                "right_classification": right_entry.classification,
            }
        )
    return {
        "left": str(left),
        "right": str(right),
        "added": sorted(right_names - left_names),
        "removed": sorted(left_names - right_names),
        "changed": changed,
        "unchanged_count": unchanged,
    }


def _entry_digest(entry: CpioEntry) -> tuple[int, str]:
    """Return size and content hash for fast equality checks."""

    return entry.size, _entry_hash(entry)


def _entry_hash(entry: CpioEntry) -> str:
    """Return the SHA-256 hash of a record payload."""

    return hashlib.sha256(entry.content).hexdigest()


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
