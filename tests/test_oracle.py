from pathlib import Path

from hip_reader import HipFile, compare_oracle

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hip" / "generated"


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
