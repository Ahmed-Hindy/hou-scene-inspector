from pathlib import Path

import struct

from hip_reader import (
    ChannelReference,
    HipFile,
    parse_parms,
    parse_spareparm_templates,
    parse_userdata,
    read_entries,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "hip" / "generated"
SOURCE_TRUTH = ROOT / "tests" / "fixtures" / "hip" / "source_truth"


def _record_text(hip_name: str, record_name: str) -> str:
    for entry in read_entries(FIXTURES / hip_name):
        if entry.name == record_name:
            return entry.text()
    raise AssertionError(f"Missing record {record_name}")


def test_parm_parser_keeps_quoted_expressions_with_parentheses() -> None:
    parms = parse_parms(_record_text("one_geo_with_box.hip", "obj/geo1.parm"))

    value = parms["ar_vdb_file"].value

    assert isinstance(value, str)
    assert 'pythonexprs("hou.pwd().path()[1:].replace(' in value
    assert value.endswith('.$F4.vdb')


def test_parm_parser_preserves_channel_references() -> None:
    hip = HipFile.load(FIXTURES / "one_geo_with_box.hip")
    geo = hip.node("/obj/geo1")

    assert geo is not None
    value = geo.parm("ar_matte")

    assert isinstance(value, ChannelReference)
    assert value.name == "ar_matte"
    assert value.channel == "ar_matte"
    assert value.value == 0
    assert value.default == 0
    assert geo.parms["ar_matte"].is_driven
    assert geo.parms["ar_matte"].channel_references == (value,)
    assert not geo.parms["vm_matte"].is_driven


def test_spareparmdef_uses_template_parser_not_parm_value_parser() -> None:
    templates = parse_spareparm_templates(
        _record_text("one_geo_with_box.hip", "obj/geo1.spareparmdef")
    )

    names = {template.name for template in templates}
    assert len(templates) > 100
    assert "xOrd" in names
    assert "vm_shadingquality" in names


def test_custom_spareparm_templates_include_schema_fields() -> None:
    hip = HipFile.load(FIXTURES / "custom_spare_parms.hip")
    geo = hip.node("/obj/geo1")

    assert geo is not None
    templates = {template.name: template for template in geo.spareparm_templates}
    custom_int = templates["custom_int"]
    custom_menu = templates["custom_menu"]
    xord = templates["xOrd"]
    rord = templates["rOrd"]
    lookat = templates["lookatpath"]
    velocity_blur = templates["geo_velocityblur"]
    subd_style = templates["vm_subdstyle"]

    assert custom_int.folder_label == "Custom Folder"
    assert custom_int.type_name == "integer"
    assert custom_int.default == ("7",)
    assert custom_int.range == ("0", "10")
    assert custom_menu.type_name == "ordinal"
    assert custom_menu.menu == (("a", "Option A"), ("b", "Option B"))
    assert xord.export == "none"
    assert xord.join_next
    assert rord.no_label
    assert lookat.invisible
    assert velocity_blur.disable_when == "{ allowmotionblur == 0 }"
    assert subd_style.hide_when == "{ vm_rendersubd == 0 }"


def test_unknown_userdata_types_preserve_type_tag_and_raw_bytes() -> None:
    data = (
        struct.pack(">I", 1)
        + struct.pack(">H", 7)
        + b"mystery"
        + struct.pack(">I", 99)
        + struct.pack(">H", 3)
        + b"\x01\x02\x03"
    )

    assert parse_userdata(data) == {
        "mystery": {"_type": 99, "_raw": b"\x01\x02\x03"}
    }


def test_userdata_fixture_exposes_saved_string_values() -> None:
    hip = HipFile.load(FIXTURES / "userdata_string_int_float.hip")
    geo = hip.node("/obj/geo1")

    assert geo is not None
    assert geo.userdata["string_value"] == "hello"
    assert geo.userdata["int_value"] == "42"
    assert geo.userdata["float_value"] == "3.5"


def test_source_truth_animation_curve_segments_keep_bezier_shape_fields() -> None:
    hip = HipFile.load(SOURCE_TRUTH / "animation_curve_variants.hip")
    transform = hip.node("/obj/geo1/transform1")

    assert transform is not None
    tx = transform.channels["tx"]
    ty = transform.channels["ty"]

    assert len(tx.segments) == 3
    assert tx.segments[0].values == (0.0, 1.0)
    assert tx.segments[0].slopes == (0.0, 1.5333024976873266)
    assert tx.segments[0].accelerations == (
        0.3194444444444444,
        0.584768036381502,
    )
    assert tx.segments[1].length == 0.9999999999999999
    assert ty.segments[0].expression == "$F * 0.1"
