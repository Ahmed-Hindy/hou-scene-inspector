from pathlib import Path

from hip_reader import HipFile

ROOT = Path(__file__).resolve().parents[1]


def test_empty_scene_has_metadata_but_no_operator_nodes() -> None:
    hip = HipFile.load(ROOT / "empty.hip")

    assert repr(hip) == (
        "HipFile(version='21.0.631', fps=24.0, "
        "frame_range=(1.0, 240.0), nodes=0)"
    )
    assert hip.variables["HIPNAME"] == "empty"
    assert hip.save_time == "Mon May 25 16:10:12 2026"
    assert hip.all_nodes() == []


def test_one_geo_node_scene() -> None:
    hip = HipFile.load(ROOT / "one_geo_node.hip")
    geo = hip.node("/obj/geo1")

    assert geo is not None
    assert geo.node_type == "geo"
    assert geo.definition is not None
    assert geo.definition.position == (-4.38333, -1.18333)
    assert geo.userdata == {"___Version___": "21.0.631"}
    assert [(node.path, node.node_type) for node in hip.all_nodes()] == [
        ("/obj/geo1", "geo")
    ]


def test_nested_box_scene_graph_and_parameters() -> None:
    hip = HipFile.load(ROOT / "one_geo_with_box.hip")
    geo = hip.node("/obj/geo1")
    box = hip.node("/obj/geo1/box1")

    assert geo is not None
    assert box is not None
    assert geo.children["box1"] is box
    assert box.node_type == "box"
    assert box.parm("size") == [1, 1, 1]
    assert box.parm("type") == "polymesh"
    assert box.definition is not None
    assert box.definition.position == (-4.31667, -1.18333)
    assert [(node.path, node.node_type) for node in hip.all_nodes()] == [
        ("/obj/geo1", "geo"),
        ("/obj/geo1/box1", "box"),
    ]


def test_connected_sop_scene_exposes_def_connections() -> None:
    hip = HipFile.load(ROOT / "box_wired_xform.hip")
    geo = hip.node("/obj/geo1")
    box = hip.node("/obj/geo1/box1")
    transform = hip.node("/obj/geo1/transform1")

    assert geo is not None
    assert box is not None
    assert transform is not None
    assert geo.child_order == ["box1", "transform1"]
    assert geo.net == "1\n"

    assert box.definition is not None
    assert box.definition.position == (-4.31667, -1.18333)
    assert box.definition.outputs[0].index == 0
    assert box.definition.outputs[0].name == "output1"
    assert not box.definition.inputs

    assert transform.definition is not None
    assert transform.definition.position == (-4.31667, -2.9598)
    assert transform.definition.inputs[0].index == 0
    assert transform.definition.inputs[0].source_node == "box1"
    assert transform.definition.inputs[0].source_output == 0
    assert transform.definition.inputs[0].connector_id == 1
    assert transform.definition.named_inputs[0].name == "input1"
    assert transform.parm("group") == ""
    assert transform.parm("s") == [1, 1, 1]
