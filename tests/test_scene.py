import hashlib
from pathlib import Path

from hip_reader import HipFile

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hip" / "generated"


def test_empty_scene_has_metadata_but_no_operator_nodes() -> None:
    hip = HipFile.load(FIXTURES / "empty.hip")

    assert repr(hip) == (
        "HipFile(version='21.0.631', fps=24.0, "
        "frame_range=(1.0, 240.0), nodes=0)"
    )
    assert hip.variables["HIPNAME"] == "empty"
    assert hip.save_time
    assert hip.all_nodes() == []


def test_one_geo_node_scene() -> None:
    hip = HipFile.load(FIXTURES / "one_geo_node.hip")
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
    hip = HipFile.load(FIXTURES / "one_geo_with_box.hip")
    geo = hip.node("/obj/geo1")
    box = hip.node("/obj/geo1/box1")

    assert geo is not None
    assert box is not None
    assert geo.children["box1"] is box
    assert box.node_type == "box"
    assert box.parm("size") == [1, 1, 1]
    assert box.parm("type") == "poly"
    assert box.definition is not None
    assert box.definition.position == (-4.31667, -1.18333)
    assert [(node.path, node.node_type) for node in hip.all_nodes()] == [
        ("/obj/geo1", "geo"),
        ("/obj/geo1/box1", "box"),
    ]


def test_connected_sop_scene_exposes_def_connections() -> None:
    hip = HipFile.load(FIXTURES / "box_wired_xform.hip")
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


def test_merge_and_fanout_connections_are_resolved() -> None:
    merge = HipFile.load(FIXTURES / "merge_two_boxes.hip")
    fanout = HipFile.load(FIXTURES / "fanout_box_to_two_xforms.hip")

    assert [
        (edge.source_path, edge.destination_path, edge.destination_input)
        for edge in merge.connections()
    ] == [
        ("/obj/geo1/box1", "/obj/geo1/merge1", 0),
        ("/obj/geo1/box2", "/obj/geo1/merge1", 1),
    ]
    assert [
        (edge.source_path, edge.destination_path)
        for edge in fanout.connections()
    ] == [
        ("/obj/geo1/box1", "/obj/geo1/xform1"),
        ("/obj/geo1/box1", "/obj/geo1/xform2"),
    ]


def test_flags_and_static_parameters() -> None:
    flags_hip = HipFile.load(FIXTURES / "bypass_template_flags.hip")
    parm_hip = HipFile.load(FIXTURES / "parm_changed_transform.hip")

    box = flags_hip.node("/obj/geo1/box1")
    xform = flags_hip.node("/obj/geo1/xform1")
    changed = parm_hip.node("/obj/geo1/xform1")

    assert box is not None and box.definition is not None
    assert xform is not None and xform.definition is not None
    assert changed is not None
    assert box.definition.flags.template
    assert xform.definition.flags.bypass
    assert changed.parm("t") == [1, 2, 3]
    assert changed.parm("r") == [10, 20, 30]
    assert changed.parm("s") == [2, 3, 4]


def test_channels_and_takes_are_structured() -> None:
    animated = HipFile.load(FIXTURES / "animated_translate.hip")
    expression = HipFile.load(FIXTURES / "expression_driven_parm.hip")
    takes = HipFile.load(FIXTURES / "two_takes_changed_parm.hip")

    animated_tx = animated.node("/obj/geo1/xform1").channels["tx"]
    expression_tx = expression.node("/obj/geo1/xform1").channels["tx"]
    animated_links = animated.node("/obj/geo1/xform1").driven_parm_links()

    assert animated_tx.is_keyframed
    assert len(animated_tx.segments) == 2
    assert animated_tx.segments[0].length == 0.9583333333333334
    assert animated_tx.segments[0].values == (0.0, 10.0)
    assert animated_links[0].parm_name == "t"
    assert animated_links[0].component_index == 0
    assert animated_links[0].channel is animated_tx
    assert expression_tx.is_expression
    assert expression_tx.segments[0].expression == "$F * 2"
    assert [take.name for take in takes.takes] == ["Main", "Alt"]
    assert takes.takes[0].overrides[0].path == "/obj/geo1/xform1"
    assert takes.takes[0].overrides[0].parm == "t"
    assert takes.takes[0].overrides[0].parms["t"].value == [0, 0, 0]
    assert takes.takes[1].overrides[0].parms["t"].value == [9, 0, 0]


def test_contexts_subnets_binary_and_black_box_hda_placeholder() -> None:
    contexts = HipFile.load(FIXTURES / "rop_and_materials.hip")
    subnet = HipFile.load(FIXTURES / "subnet_inside_geo.hip")
    locked = HipFile.load(FIXTURES / "locked_geometry_or_stash.hip")
    hda = HipFile.load(FIXTURES / "simple_hda_instance.hip")

    assert contexts.node("/out/geometry1").node_type == "geometry"
    assert contexts.node("/mat/principledshader1").node_type == "principledshader::2.0"
    assert subnet.node("/obj/geo1/subnet1/xform1").inputs[0].source_node == "box1"
    assert locked.node("/obj/geo1/box1").definition.flags.hard_locked
    assert "data" in locked.node("/obj/geo1/box1").binary_records
    binary_info = locked.node("/obj/geo1/box1").binary_record_infos()[0]
    assert binary_info.record_name == "obj/geo1/box1.data"
    assert binary_info.classification == "binary"
    assert binary_info.size == len(locked.node("/obj/geo1/box1").binary_records["data"])
    assert binary_info.sha256 == hashlib.sha256(
        locked.node("/obj/geo1/box1").binary_records["data"]
    ).hexdigest()
    assert binary_info.preview_hex.startswith("7f 4e 53 4a")
    assert locked.binary_record_summary() == [binary_info]
    assert hda.node("/obj/simple_hda1").node_type == "hip_reader_simple_hda::1.0"
    assert hda.node("/obj/simple_hda1").userdata["hda_fixture_note"] == "real hda instance"
    assert hda.node("/obj/simple_hda1/inner_geo").node_type == "geo"
