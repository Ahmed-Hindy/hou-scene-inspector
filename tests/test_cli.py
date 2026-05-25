import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hip"
GOLDEN = ROOT / "tests" / "fixtures" / "golden"


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "hip_reader.cli", *args],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def test_summary_json_exports_scene_graph() -> None:
    result = run_cli("summary", "--json", str(FIXTURES / "merge_two_boxes.hip"))
    payload = json.loads(result.stdout)

    assert payload["houdini_version"] == "21.0.631"
    assert len(payload["connections"]) == 2
    assert payload["connections"][0]["source_path"] == "/obj/geo1/box1"


def test_records_json_and_dump_record() -> None:
    records = run_cli("records", "--json", str(FIXTURES / "locked_geometry_or_stash.hip"))
    payload = json.loads(records.stdout)
    data_record = next(item for item in payload if item["name"] == "obj/geo1/box1.data")

    assert data_record["classification"] == "binary"

    dumped = run_cli(
        "dump-record",
        "--json",
        str(FIXTURES / "box_wired_xform.hip"),
        "obj/geo1/transform1.def",
    )
    dump_payload = json.loads(dumped.stdout)
    assert dump_payload["classification"] == "text"
    assert "inputsNamed3" in dump_payload["text"]


def test_node_and_tree_json_exports() -> None:
    node = run_cli(
        "node",
        "--json",
        str(FIXTURES / "animated_translate.hip"),
        "/obj/geo1/xform1",
    )
    tree = run_cli("tree", "--json", str(FIXTURES / "subnet_inside_geo.hip"))

    node_payload = json.loads(node.stdout)
    tree_payload = json.loads(tree.stdout)

    assert "tx" in node_payload["channels"]
    assert tree_payload["obj"][0]["children"][0]["name"] == "subnet1"


def test_tree_json_matches_golden_snapshot() -> None:
    result = run_cli("tree", "--json", str(FIXTURES / "subnet_inside_geo.hip"))

    assert json.loads(result.stdout) == json.loads(
        (GOLDEN / "subnet_inside_geo_tree.json").read_text()
    )
