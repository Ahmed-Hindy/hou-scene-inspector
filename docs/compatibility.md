# Compatibility Notes

`hip-reader` is a Houdini-free inspector for saved `.hip` scene structure. It
does not cook nodes, evaluate geometry, render, execute HDAs, or import `hou` at
runtime.

## Supported

- Houdini 21.0 `.hip` files saved as old portable CPIO archives.
- Archive record listing, payload classification, and exact record dumping.
- Global scene metadata from `.start` and `.variables`.
- Node hierarchy from record paths, including nested subnets.
- Node metadata from `.def`: position, common flags, stat block, named outputs,
  input blocks, and simple resolved graph edges.
- Parameter values from `.parm`, including strings with parentheses and
  bracketed channel references.
- Channel inspection from `.chn`: channel names, defaults, flags, segments,
  expressions, and segment value pairs.
- Spare parameter template inspection for names, labels, type names, defaults,
  folder labels, and menu item pairs.
- Saved string userdata and preservation of unknown userdata type tags.
- Binary payload preservation for records such as hard-locked SOP `.data`.
- Take name and child-count listing from `.takes`.
- JSON exports for records, summary, tree, and individual nodes.

## Known Unknowns

- `.net` has only been observed as the `1\n` sentinel in the current corpus;
  SOP wiring is currently proven through node `.def` input blocks instead.
- Userdata type tags beyond observed type `3` are preserved but not decoded.
- Channel timing is inspectable as saved segment lengths and values, not
  converted into fully evaluated keyframe curves.
- HDA fixtures are currently black-box metadata placeholders; real HDA
  definition parsing is not implemented.
- Binary geometry payloads are classified and preserved, not decoded.

## Fixture Rule

Fixtures may be generated with `hython` using `tools/houdini/generate_fixtures.py`.
Runtime package code and runtime tests must remain pure Python and must not
import `hou`.
