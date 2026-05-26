"""Batch comparison helpers for Houdini oracle snapshots."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hip_reader.oracle import compare_oracle, load_oracle
from hip_reader.scene import HipFile


@dataclass(frozen=True)
class OracleMatrixOptions:
    """Options for running a fixture-to-oracle comparison matrix."""

    fixture_root: Path
    oracle_dir: Path
    exporter: Path = Path("tools/houdini/export_oracle.py")
    hython: Path = Path("hython")
    export_missing: bool = False
    refresh: bool = False


def discover_hip_files(fixture_root: Path) -> list[Path]:
    """Return all ``.hip`` files under ``fixture_root`` in deterministic order."""

    return sorted(path for path in fixture_root.rglob("*.hip") if path.is_file())


def oracle_path_for(hip_file: Path, fixture_root: Path, oracle_dir: Path) -> Path:
    """Return the expected oracle JSON path for ``hip_file``."""

    try:
        relative = hip_file.resolve().relative_to(fixture_root.resolve())
    except ValueError:
        relative = Path(hip_file.name)
    return (oracle_dir / relative).with_name(f"{relative.stem}.oracle.json")


def run_oracle_matrix(
    hip_files: list[Path],
    options: OracleMatrixOptions,
) -> dict[str, Any]:
    """Compare ``hip_files`` against oracle JSON files."""

    cases = [_run_case(path, options) for path in hip_files]
    return {
        "fixture_root": str(options.fixture_root),
        "oracle_dir": str(options.oracle_dir),
        "case_count": len(cases),
        "summary": _status_counts(cases),
        "cases": cases,
    }


def format_matrix_report(payload: dict[str, Any]) -> str:
    """Return a Markdown coverage report for an oracle matrix payload."""

    summary = payload["summary"]
    lines = [
        "# Houdini Oracle Coverage",
        "",
        "This report compares `hip-reader` output with Houdini API oracle JSON.",
        "",
        "## Summary",
        "",
        f"- Fixtures: {payload['case_count']}",
        f"- Matched: {summary.get('matched', 0)}",
        f"- Mismatched: {summary.get('mismatch', 0)}",
        f"- Missing oracle: {summary.get('missing_oracle', 0)}",
        f"- Export failed: {summary.get('export_failed', 0)}",
        f"- Compare failed: {summary.get('compare_failed', 0)}",
        "",
        "## Cases",
        "",
        "| Status | Fixture | Nodes | Connections | Channels | Takes | Mismatches |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for case in payload["cases"]:
        summary = case.get("comparison", {}).get("summary", {})
        lines.append(
            "| "
            f"{case['status']} | "
            f"`{case['hip_file']}` | "
            f"{summary.get('hip_nodes', '')} | "
            f"{summary.get('hip_connections', '')} | "
            f"{summary.get('hip_channels', '')} | "
            f"{summary.get('hip_takes', '')} | "
            f"{case.get('mismatch_count', '')} |"
        )

    mismatch_cases = [
        case for case in payload["cases"] if case.get("mismatch_count", 0) > 0
    ]
    if mismatch_cases:
        lines.extend(["", "## Mismatches", ""])
        for case in mismatch_cases:
            lines.append(f"### `{case['hip_file']}`")
            lines.append("")
            for mismatch in case["comparison"]["mismatches"]:
                lines.append(
                    "- "
                    f"{mismatch['kind']} at `{mismatch['path']}`: "
                    f"hip-reader={_short_repr(mismatch['hip_reader'])}, "
                    f"oracle={_short_repr(mismatch['oracle'])}"
                )
            lines.append("")

    issue_cases = [
        case
        for case in payload["cases"]
        if case["status"] in {"missing_oracle", "export_failed", "compare_failed"}
    ]
    if issue_cases:
        lines.extend(["", "## Incomplete Cases", ""])
        for case in issue_cases:
            reason = case.get("error") or case["status"]
            lines.append(f"- `{case['hip_file']}`: {reason}")

    return "\n".join(lines).rstrip() + "\n"


def _run_case(hip_file: Path, options: OracleMatrixOptions) -> dict[str, Any]:
    """Run one fixture comparison case."""

    oracle_path = oracle_path_for(hip_file, options.fixture_root, options.oracle_dir)
    if options.refresh or (options.export_missing and not oracle_path.exists()):
        export = _export_oracle(hip_file, oracle_path, options)
        if export["status"] != "exported":
            return {
                "hip_file": _display_path(hip_file, options.fixture_root),
                "oracle_json": str(oracle_path),
                "status": "export_failed",
                "error": export["error"],
                "export": export,
            }

    if not oracle_path.exists():
        return {
            "hip_file": _display_path(hip_file, options.fixture_root),
            "oracle_json": str(oracle_path),
            "status": "missing_oracle",
            "mismatch_count": 0,
        }

    try:
        comparison = compare_oracle(HipFile.load(hip_file), load_oracle(oracle_path))
    except Exception as exc:  # pragma: no cover - defensive report path.
        return {
            "hip_file": _display_path(hip_file, options.fixture_root),
            "oracle_json": str(oracle_path),
            "status": "compare_failed",
            "error": str(exc),
            "mismatch_count": 0,
        }
    return {
        "hip_file": _display_path(hip_file, options.fixture_root),
        "oracle_json": str(oracle_path),
        "status": "matched" if comparison["ok"] else "mismatch",
        "mismatch_count": comparison["mismatch_count"],
        "comparison": comparison,
    }


def _export_oracle(
    hip_file: Path,
    oracle_path: Path,
    options: OracleMatrixOptions,
) -> dict[str, Any]:
    """Export one oracle JSON file with ``hython``."""

    command = [
        str(options.hython),
        str(options.exporter),
        str(hip_file),
        "--output",
        str(oracle_path),
        "--source-root",
        str(options.fixture_root),
        "--pretty",
    ]
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        return {
            "status": "failed",
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
            "error": f"hython exited with {completed.returncode}",
        }
    if not oracle_path.exists():
        return {
            "status": "failed",
            "command": command,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
            "error": "hython completed but did not write the oracle JSON",
        }
    return {
        "status": "exported",
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _status_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    """Return result counts by status."""

    counts = {
        "matched": 0,
        "mismatch": 0,
        "missing_oracle": 0,
        "export_failed": 0,
        "compare_failed": 0,
    }
    for case in cases:
        counts[case["status"]] = counts.get(case["status"], 0) + 1
    return counts


def _display_path(path: Path, fixture_root: Path) -> str:
    """Return a stable display path for reports."""

    try:
        return path.resolve().relative_to(fixture_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _short_repr(value: Any, *, limit: int = 120) -> str:
    """Return a compact JSON-ish representation."""

    text = json.dumps(value, sort_keys=True)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _tail(text: str, *, lines: int = 20) -> str:
    """Return the final lines of captured process output."""

    return "\n".join(text.splitlines()[-lines:])
