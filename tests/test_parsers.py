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


def _record_text(hip_name: str, record_name: str) -> str:
    for entry in read_entries(ROOT / hip_name):
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
    hip = HipFile.load(ROOT / "one_geo_with_box.hip")
    geo = hip.node("/obj/geo1")

    assert geo is not None
    value = geo.parm("ar_matte")

    assert isinstance(value, ChannelReference)
    assert value.name == "ar_matte"
    assert value.channel == "ar_matte"
    assert value.value == 0
    assert value.default == 0
    assert geo.parms["ar_matte"].is_driven
    assert not geo.parms["vm_matte"].is_driven


def test_spareparmdef_uses_template_parser_not_parm_value_parser() -> None:
    templates = parse_spareparm_templates(
        _record_text("one_geo_with_box.hip", "obj/geo1.spareparmdef")
    )

    names = {template.name for template in templates}
    assert len(templates) > 100
    assert "xOrd" in names
    assert "vm_shadingquality" in names


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
