"""Compare ``hip_reader`` output with a Houdini-exported oracle snapshot."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from hip_reader.scene import HipFile


def load_oracle(path: str | Path) -> dict[str, Any]:
    """Load an oracle JSON document exported by ``tools/houdini/export_oracle.py``."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def compare_oracle(
    hip: HipFile,
    oracle: dict[str, Any],
    *,
    position_tolerance: float = 1e-4,
) -> dict[str, Any]:
    """Compare a loaded ``HipFile`` against a Houdini oracle snapshot.

    The comparison is intentionally structural. It does not evaluate geometry,
    expressions, or animation curves.
    """

    mismatches: list[dict[str, Any]] = []
    _compare_nodes(hip, oracle, mismatches, position_tolerance)
    _compare_connections(hip, oracle, mismatches)
    _compare_takes(hip, oracle, mismatches)
    _compare_channels(hip, oracle, mismatches)
    _compare_static_parms(hip, oracle, mismatches)

    return {
        "ok": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "summary": {
            "hip_nodes": len(hip.all_nodes()),
            "oracle_nodes": len(oracle.get("nodes", [])),
            "hip_connections": len(hip.connections()),
            "oracle_connections": len(oracle.get("connections", [])),
            "hip_takes": len(hip.takes),
            "oracle_takes": len(oracle.get("takes", [])),
            "hip_channels": sum(len(node.channels) for node in hip.all_nodes()),
            "oracle_channels": sum(
                len(node.get("channels", {})) for node in oracle.get("nodes", [])
            ),
        },
    }


def _compare_nodes(
    hip: HipFile,
    oracle: dict[str, Any],
    mismatches: list[dict[str, Any]],
    position_tolerance: float,
) -> None:
    """Compare node paths, types, children, and positions."""

    hip_nodes = {node.path: node for node in hip.all_nodes()}
    oracle_nodes = {node["path"]: node for node in oracle.get("nodes", [])}
    _compare_key_sets(
        "nodes",
        set(hip_nodes),
        set(oracle_nodes),
        mismatches,
    )
    for path in sorted(set(hip_nodes) & set(oracle_nodes)):
        hip_node = hip_nodes[path]
        oracle_node = oracle_nodes[path]
        if hip_node.node_type != oracle_node.get("node_type"):
            _add_mismatch(
                mismatches,
                "node_type",
                path,
                hip_node.node_type,
                oracle_node.get("node_type"),
            )
        hip_children = sorted(child.path for child in hip_node.children.values())
        oracle_children = sorted(oracle_node.get("children", []))
        if hip_children != oracle_children:
            _add_mismatch(mismatches, "children", path, hip_children, oracle_children)
        if hip_node.definition is not None:
            hip_position = hip_node.definition.position
            oracle_position = tuple(oracle_node.get("position", (0.0, 0.0)))
            if not _float_pairs_close(
                hip_position,
                oracle_position,
                tolerance=position_tolerance,
            ):
                _add_mismatch(
                    mismatches,
                    "position",
                    path,
                    list(hip_position),
                    list(oracle_position),
                )


def _compare_connections(
    hip: HipFile,
    oracle: dict[str, Any],
    mismatches: list[dict[str, Any]],
) -> None:
    """Compare resolved connection endpoints."""

    hip_connections = {
        (
            connection.source_path,
            connection.source_output,
            connection.destination_path,
            connection.destination_input,
        )
        for connection in hip.connections()
    }
    oracle_connections = {
        (
            connection["source_path"],
            connection["source_output"],
            connection["destination_path"],
            connection["destination_input"],
        )
        for connection in oracle.get("connections", [])
    }
    _compare_key_sets(
        "connections",
        hip_connections,
        oracle_connections,
        mismatches,
    )


def _compare_takes(
    hip: HipFile,
    oracle: dict[str, Any],
    mismatches: list[dict[str, Any]],
) -> None:
    """Compare take names."""

    hip_takes = [take.name for take in hip.takes]
    oracle_takes = [take["name"] for take in oracle.get("takes", [])]
    if hip_takes != oracle_takes:
        _add_mismatch(mismatches, "takes", ".takes", hip_takes, oracle_takes)


def _compare_channels(
    hip: HipFile,
    oracle: dict[str, Any],
    mismatches: list[dict[str, Any]],
) -> None:
    """Compare expression channels and keyframe counts/values."""

    hip_nodes = {node.path: node for node in hip.all_nodes()}
    for oracle_node in oracle.get("nodes", []):
        hip_node = hip_nodes.get(oracle_node["path"])
        if hip_node is None:
            continue
        for channel_name, oracle_channel in oracle_node.get("channels", {}).items():
            hip_channel = hip_node.channels.get(channel_name)
            label = f"{hip_node.path}.{channel_name}"
            if hip_channel is None:
                _add_mismatch(mismatches, "channel", label, None, oracle_channel)
                continue
            expression = oracle_channel.get("expression") or ""
            keyframes = oracle_channel.get("keyframes", [])
            if expression:
                hip_expression = (
                    hip_channel.segments[0].expression if hip_channel.segments else ""
                )
                if _normalize_expression(hip_expression) != _normalize_expression(expression):
                    _add_mismatch(
                        mismatches,
                        "channel_expression",
                        label,
                        hip_expression,
                        expression,
                    )
            if keyframes:
                if any(not segment.values for segment in hip_channel.segments):
                    continue
                if len(hip_channel.segments) != len(keyframes):
                    _add_mismatch(
                        mismatches,
                        "channel_keyframe_count",
                        label,
                        len(hip_channel.segments),
                        len(keyframes),
                    )
                    continue
                hip_values = [
                    segment.values[0]
                    for segment in hip_channel.segments
                    if segment.values
                ]
                oracle_values = [keyframe["value"] for keyframe in keyframes]
                if not _float_sequences_close(hip_values, oracle_values):
                    _add_mismatch(
                        mismatches,
                        "channel_key_values",
                        label,
                        hip_values,
                        oracle_values,
                    )


def _compare_static_parms(
    hip: HipFile,
    oracle: dict[str, Any],
    mismatches: list[dict[str, Any]],
) -> None:
    """Compare simple, non-driven parameter tuple raw values."""

    hip_nodes = {node.path: node for node in hip.all_nodes()}
    for oracle_node in oracle.get("nodes", []):
        hip_node = hip_nodes.get(oracle_node["path"])
        if hip_node is None:
            continue
        driven_tuples = {
            channel.get("parm_tuple")
            for channel in oracle_node.get("channels", {}).values()
        }
        for parm_name, oracle_parm in oracle_node.get("parms", {}).items():
            if parm_name in driven_tuples:
                continue
            hip_parm = hip_node.parms.get(parm_name)
            if hip_parm is None:
                continue
            hip_values = [_normalize_raw_value(value) for value in hip_parm.raw_values]
            oracle_values = [
                _normalize_raw_value(value)
                for value in oracle_parm.get("raw_values", [])
            ]
            if len(hip_values) != len(oracle_values):
                continue
            if not _raw_values_are_comparable(hip_values, oracle_values):
                continue
            if hip_values != oracle_values:
                _add_mismatch(
                    mismatches,
                    "parm_raw_values",
                    f"{hip_node.path}.{parm_name}",
                    hip_values,
                    oracle_values,
                )


def _compare_key_sets(
    kind: str,
    hip_values: set[Any],
    oracle_values: set[Any],
    mismatches: list[dict[str, Any]],
) -> None:
    """Add missing/extra set mismatches."""

    missing = sorted(oracle_values - hip_values)
    extra = sorted(hip_values - oracle_values)
    if missing:
        _add_mismatch(mismatches, f"{kind}_missing", kind, [], missing)
    if extra:
        _add_mismatch(mismatches, f"{kind}_extra", kind, extra, [])


def _add_mismatch(
    mismatches: list[dict[str, Any]],
    kind: str,
    path: str,
    hip_value: Any,
    oracle_value: Any,
) -> None:
    """Append one normalized mismatch entry."""

    mismatches.append(
        {
            "kind": kind,
            "path": path,
            "hip_reader": hip_value,
            "oracle": oracle_value,
        }
    )


def _normalize_raw_value(value: Any) -> str:
    """Normalize raw parm tokens for comparison."""

    text = str(value)
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return text.replace(r"\"", '"')


def _normalize_expression(value: str) -> str:
    """Normalize equivalent expression quoting from saved text and hou APIs."""

    return value.replace(r"\"", '"')


def _raw_values_are_comparable(left: list[str], right: list[str]) -> bool:
    """Return whether two raw parm value lists use the same obvious domain."""

    for left_value, right_value in zip(left, right):
        if _is_number(left_value) != _is_number(right_value):
            return False
    return True


def _is_number(value: str) -> bool:
    """Return whether a string is numeric."""

    try:
        float(value)
    except ValueError:
        return False
    return True


def _float_pairs_close(
    left: tuple[float, float],
    right: tuple[float, float],
    *,
    tolerance: float,
) -> bool:
    """Return whether two 2D float tuples are close."""

    return all(math.isclose(a, b, abs_tol=tolerance) for a, b in zip(left, right))


def _float_sequences_close(
    left: list[float],
    right: list[float],
    *,
    tolerance: float = 1e-6,
) -> bool:
    """Return whether two float sequences are close."""

    if len(left) != len(right):
        return False
    return all(math.isclose(a, b, abs_tol=tolerance) for a, b in zip(left, right))
