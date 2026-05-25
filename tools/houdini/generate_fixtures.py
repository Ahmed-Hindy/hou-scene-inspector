"""Generate controlled Houdini .hip fixtures for hip-reader.

Run with Houdini's ``hython``. This script is intentionally outside the runtime
package: fixtures may use Houdini as an oracle, but ``hip_reader`` must not.
"""

from __future__ import annotations

from pathlib import Path

import hou

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "hip"


def main() -> None:
    """Generate all controlled reverse-engineering fixtures."""

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    make_empty()
    make_one_geo_node()
    make_one_geo_with_box()
    make_box_wired_xform()
    make_two_geo_nodes()
    make_renamed_node()
    make_nested_subnet()
    make_merge_two_boxes()
    make_fanout_box_to_two_xforms()
    make_bypass_template_flags()
    make_parm_changed_transform()
    make_string_expression_parm()
    make_animated_translate()
    make_expression_driven_parm()
    make_mixed_static_animated()
    make_custom_spare_parms()
    make_userdata_string_int_float()
    make_locked_geometry_or_stash()
    make_rop_and_materials()
    make_subnet_inside_geo()
    make_simple_hda_instance()
    make_two_takes_changed_parm()


def reset_scene() -> None:
    """Clear the current Houdini scene."""

    hou.hipFile.clear(suppress_save_prompt=True)


def save(name: str) -> None:
    """Save the current scene into the fixture directory."""

    path = FIXTURE_DIR / name
    hou.hipFile.save(str(path))
    print(path)


def new_geo(name: str = "geo1") -> hou.Node:
    """Create an empty geometry object."""

    geo = hou.node("/obj").createNode("geo", name)
    for child in geo.children():
        child.destroy()
    return geo


def make_empty() -> None:
    reset_scene()
    save("empty.hip")


def make_one_geo_node() -> None:
    reset_scene()
    geo = new_geo()
    geo.setPosition((-4.38333, -1.18333))
    save("one_geo_node.hip")


def make_one_geo_with_box() -> None:
    reset_scene()
    geo = new_geo()
    geo.setPosition((-4.38333, -1.18333))
    box = geo.createNode("box", "box1")
    box.setPosition((-4.31667, -1.18333))
    save("one_geo_with_box.hip")


def make_box_wired_xform() -> None:
    reset_scene()
    geo = new_geo()
    geo.setPosition((-4.38333, -1.18333))
    box = geo.createNode("box", "box1")
    xform = geo.createNode("xform", "transform1")
    box.setPosition((-4.31667, -1.18333))
    xform.setPosition((-4.31667, -2.9598))
    xform.setInput(0, box)
    save("box_wired_xform.hip")


def make_two_geo_nodes() -> None:
    reset_scene()
    geo1 = new_geo("geo1")
    geo2 = new_geo("geo2")
    geo1.setPosition((-4, -1))
    geo2.setPosition((-2, -1))
    save("two_geo_nodes.hip")


def make_renamed_node() -> None:
    reset_scene()
    geo = new_geo("myGeo")
    geo.setPosition((-4, -1))
    save("renamed_node.hip")


def make_nested_subnet() -> None:
    reset_scene()
    geo = new_geo()
    subnet = geo.createNode("subnet", "subnet1")
    box = subnet.createNode("box", "box1")
    subnet.setPosition((-4, -1))
    box.setPosition((-4, -1))
    save("nested_subnet.hip")


def make_merge_two_boxes() -> None:
    reset_scene()
    geo = new_geo()
    box1 = geo.createNode("box", "box1")
    box2 = geo.createNode("box", "box2")
    merge = geo.createNode("merge", "merge1")
    merge.setInput(0, box1)
    merge.setInput(1, box2)
    box1.setPosition((-5, -1))
    box2.setPosition((-3, -1))
    merge.setPosition((-4, -3))
    save("merge_two_boxes.hip")


def make_fanout_box_to_two_xforms() -> None:
    reset_scene()
    geo = new_geo()
    box = geo.createNode("box", "box1")
    xform1 = geo.createNode("xform", "xform1")
    xform2 = geo.createNode("xform", "xform2")
    xform1.setInput(0, box)
    xform2.setInput(0, box)
    box.setPosition((-4, -1))
    xform1.setPosition((-5, -3))
    xform2.setPosition((-3, -3))
    save("fanout_box_to_two_xforms.hip")


def make_bypass_template_flags() -> None:
    reset_scene()
    geo = new_geo()
    box = geo.createNode("box", "box1")
    xform = geo.createNode("xform", "xform1")
    xform.setInput(0, box)
    box.setTemplateFlag(True)
    xform.bypass(True)
    box.setDisplayFlag(False)
    xform.setDisplayFlag(True)
    save("bypass_template_flags.hip")


def make_parm_changed_transform() -> None:
    reset_scene()
    geo = new_geo()
    xform = geo.createNode("xform", "xform1")
    xform.parmTuple("t").set((1, 2, 3))
    xform.parmTuple("r").set((10, 20, 30))
    xform.parmTuple("s").set((2, 3, 4))
    save("parm_changed_transform.hip")


def make_string_expression_parm() -> None:
    reset_scene()
    geo = new_geo()
    template_group = geo.parmTemplateGroup()
    template_group.append(hou.StringParmTemplate("expr_text", "Expression Text", 1))
    geo.setParmTemplateGroup(template_group)
    value = "$HIP/`pythonexprs(\"hou.pwd().path()[1:].replace('/', '_')\")`.$F4.vdb"
    geo.parm("expr_text").set(value)
    save("string_expression_parm.hip")


def make_animated_translate() -> None:
    reset_scene()
    geo = new_geo()
    xform = geo.createNode("xform", "xform1")
    set_key(xform.parm("tx"), 1, 0)
    set_key(xform.parm("tx"), 24, 10)
    save("animated_translate.hip")


def make_expression_driven_parm() -> None:
    reset_scene()
    geo = new_geo()
    xform = geo.createNode("xform", "xform1")
    xform.parm("tx").setExpression("$F * 2", language=hou.exprLanguage.Hscript)
    save("expression_driven_parm.hip")


def make_mixed_static_animated() -> None:
    reset_scene()
    geo = new_geo()
    xform = geo.createNode("xform", "xform1")
    set_key(xform.parm("tx"), 1, 0)
    set_key(xform.parm("tx"), 10, 5)
    xform.parm("ty").set(5)
    xform.parm("tz").setExpression("$F", language=hou.exprLanguage.Hscript)
    save("mixed_static_animated.hip")


def make_custom_spare_parms() -> None:
    reset_scene()
    geo = new_geo()
    template_group = geo.parmTemplateGroup()
    folder = hou.FolderParmTemplate(
        "custom_folder",
        "Custom Folder",
        (
            hou.IntParmTemplate("custom_int", "Custom Int", 1, default_value=(7,)),
            hou.FloatParmTemplate("custom_float", "Custom Float", 1, default_value=(3.5,)),
            hou.StringParmTemplate("custom_string", "Custom String", 1, default_value=("hello",)),
            hou.ToggleParmTemplate("custom_toggle", "Custom Toggle", default_value=True),
            hou.MenuParmTemplate(
                "custom_menu",
                "Custom Menu",
                ("a", "b"),
                ("Option A", "Option B"),
                default_value=1,
            ),
        ),
    )
    template_group.append(folder)
    geo.setParmTemplateGroup(template_group)
    save("custom_spare_parms.hip")


def make_userdata_string_int_float() -> None:
    reset_scene()
    geo = new_geo()
    geo.setUserData("string_value", "hello")
    geo.setUserData("int_value", "42")
    geo.setUserData("float_value", "3.5")
    save("userdata_string_int_float.hip")


def make_locked_geometry_or_stash() -> None:
    reset_scene()
    geo = new_geo()
    box = geo.createNode("box", "box1")
    box.setHardLocked(True)
    save("locked_geometry_or_stash.hip")


def make_rop_and_materials() -> None:
    reset_scene()
    out = hou.node("/out")
    mat = hou.node("/mat")
    out.createNode("geometry", "geometry1")
    mat.createNode("principledshader", "principledshader1")
    save("rop_and_materials.hip")


def make_subnet_inside_geo() -> None:
    reset_scene()
    geo = new_geo()
    subnet = geo.createNode("subnet", "subnet1")
    box = subnet.createNode("box", "box1")
    xform = subnet.createNode("xform", "xform1")
    xform.setInput(0, box)
    save("subnet_inside_geo.hip")


def make_simple_hda_instance() -> None:
    reset_scene()
    subnet = hou.node("/obj").createNode("subnet", "simple_hda1")
    subnet.createNode("geo", "inner_geo")
    hda_path = FIXTURE_DIR / "simple_hda_definition.hda"
    if hda_path.exists():
        hda_path.unlink()
    hda = subnet.createDigitalAsset(
        name="hip_reader_simple_hda::1.0",
        hda_file_name=str(hda_path),
        description="hip-reader simple HDA",
    )
    hda.setUserData("hda_fixture_note", "real hda instance")
    save("simple_hda_instance.hip")


def make_two_takes_changed_parm() -> None:
    reset_scene()
    geo = new_geo()
    xform = geo.createNode("xform", "xform1")
    take = hou.takes.rootTake().addChildTake("Alt")
    hou.takes.setCurrentTake(take)
    take.addParmTuple(xform.parmTuple("t"))
    xform.parm("tx").set(9)
    hou.takes.setCurrentTake(hou.takes.rootTake())
    save("two_takes_changed_parm.hip")


def set_key(parm: hou.Parm, frame: float, value: float) -> None:
    """Set a simple keyframe on a parameter."""

    keyframe = hou.Keyframe()
    keyframe.setFrame(frame)
    keyframe.setValue(value)
    parm.setKeyframe(keyframe)


if __name__ == "__main__":
    main()
