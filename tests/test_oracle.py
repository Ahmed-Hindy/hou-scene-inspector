from pathlib import Path

from hou_scene_inspector import (
    HipFile,
    OracleMatrixOptions,
    compare_oracle,
    format_matrix_report,
    oracle_path_for,
    run_oracle_matrix,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hip" / "generated"
HIP_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "hip"
ORACLE_FIXTURES = ROOT / "tests" / "fixtures" / "oracles"


def test_committed_houdini_oracle_matrix_matches_parser() -> None:
    hip_files = sorted(HIP_FIXTURE_ROOT.rglob("*.hip"))
    payload = run_oracle_matrix(
        hip_files,
        OracleMatrixOptions(
            fixture_root=HIP_FIXTURE_ROOT,
            oracle_dir=ORACLE_FIXTURES,
        ),
    )

    assert payload["summary"]["matched"] == len(hip_files)
    assert payload["summary"]["mismatch"] == 0
    assert payload["summary"]["missing_oracle"] == 0


def test_compare_oracle_accepts_matching_structural_snapshot() -> None:
    hip = HipFile.load(FIXTURES / "merge_two_boxes.hip")

    result = compare_oracle(hip, _merge_oracle())

    assert result["ok"]
    assert result["mismatch_count"] == 0
    assert result["summary"]["hip_nodes"] == 4
    assert result["summary"]["oracle_connections"] == 2


def test_compare_oracle_reports_mismatched_node_type() -> None:
    hip = HipFile.load(FIXTURES / "merge_two_boxes.hip")
    oracle = _merge_oracle()
    oracle["nodes"][1]["node_type"] = "sphere"

    result = compare_oracle(hip, oracle)

    assert not result["ok"]
    assert result["mismatches"][0]["kind"] == "node_type"
    assert result["mismatches"][0]["path"] == "/obj/geo1/box1"
    assert "hou_scene_inspector" in result["mismatches"][0]
    assert "hip_reader" not in result["mismatches"][0]


def test_compare_oracle_treats_take_order_as_non_semantic() -> None:
    hip = HipFile.load(FIXTURES / "two_takes_changed_parm.hip")

    result = compare_oracle(
        hip,
        {
            "schema_version": 1,
            "source": "test",
            "nodes": [],
            "connections": [],
            "takes": [{"name": "Alt"}, {"name": "Main"}],
        },
    )

    assert not any(mismatch["kind"] == "takes" for mismatch in result["mismatches"])


def test_oracle_path_for_preserves_fixture_subdirs(tmp_path: Path) -> None:
    path = oracle_path_for(
        FIXTURES / "merge_two_boxes.hip",
        ROOT / "tests" / "fixtures" / "hip",
        tmp_path,
    )

    assert path == tmp_path / "generated" / "merge_two_boxes.oracle.json"


def test_oracle_matrix_reports_matching_and_missing_cases(tmp_path: Path) -> None:
    oracle_dir = tmp_path / "oracles"
    oracle_path = oracle_path_for(
        FIXTURES / "empty.hip",
        ROOT / "tests" / "fixtures" / "hip",
        oracle_dir,
    )
    oracle_path.parent.mkdir(parents=True)
    oracle_path.write_text(
        """{
          "schema_version": 1,
          "source": "test",
          "nodes": [],
          "connections": [],
          "takes": [{"name": "Main", "children": []}]
        }
        """,
        encoding="utf-8",
    )

    payload = run_oracle_matrix(
        [FIXTURES / "empty.hip", FIXTURES / "one_geo_node.hip"],
        OracleMatrixOptions(
            fixture_root=ROOT / "tests" / "fixtures" / "hip",
            oracle_dir=oracle_dir,
        ),
    )
    report = format_matrix_report(payload)

    assert payload["summary"]["matched"] == 1
    assert payload["summary"]["missing_oracle"] == 1
    assert "`generated/empty.hip`" in report
    assert "`generated/one_geo_node.hip`" in report


def _merge_oracle() -> dict[str, object]:
    """Return a compact Houdini-like oracle for merge_two_boxes.hip."""

    return {
        "schema_version": 1,
        "source": "test",
        "nodes": [
            {
                "path": "/obj/geo1",
                "name": "geo1",
                "node_type": "geo",
                "children": [
                    "/obj/geo1/box1",
                    "/obj/geo1/box2",
                    "/obj/geo1/merge1",
                ],
                "position": [0.0, 0.0],
                "parms": {},
                "channels": {},
            },
            {
                "path": "/obj/geo1/box1",
                "name": "box1",
                "node_type": "box",
                "children": [],
                "position": [-5.0, -1.0],
                "parms": {},
                "channels": {},
            },
            {
                "path": "/obj/geo1/box2",
                "name": "box2",
                "node_type": "box",
                "children": [],
                "position": [-3.0, -1.0],
                "parms": {},
                "channels": {},
            },
            {
                "path": "/obj/geo1/merge1",
                "name": "merge1",
                "node_type": "merge",
                "children": [],
                "position": [-4.0, -3.0],
                "parms": {},
                "channels": {},
            },
        ],
        "connections": [
            {
                "source_path": "/obj/geo1/box1",
                "source_output": 0,
                "destination_path": "/obj/geo1/merge1",
                "destination_input": 0,
            },
            {
                "source_path": "/obj/geo1/box2",
                "source_output": 0,
                "destination_path": "/obj/geo1/merge1",
                "destination_input": 1,
            },
        ],
        "takes": [{"name": "Main", "children": []}],
    }
