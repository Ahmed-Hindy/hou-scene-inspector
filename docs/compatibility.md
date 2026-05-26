# Compatibility Notes

`hip-reader` is a Houdini-free inspector for saved `.hip` scene structure. It
does not cook nodes, evaluate geometry, render, execute HDAs, or import `hou` at
runtime.

## Supported

- Houdini 21.0 `.hip` files saved as old portable CPIO archives.
- Archive record listing, payload classification, exact record dumping, and
  record-level diffs by name/content hash.
- Global scene metadata from `.start` and `.variables`.
- Node hierarchy from record paths, including nested subnets.
- Node metadata from `.def`: position, common flags, stat block, named outputs,
  input blocks, and simple resolved graph edges.
- Parameter values from `.parm`, including strings with parentheses and
  bracketed channel references.
- Channel inspection from `.chn`: channel names, defaults, flags, segments,
  expressions, segment value pairs, slopes, and acceleration fields.
- Driven parameter links from `.parm` channel references to matching local
  `.chn` records.
- Spare parameter template inspection for names, labels, type names, defaults,
  ranges, folder labels, menu item pairs, common UI flags, export settings, and
  observed hide/disable conditions.
- Saved string userdata and preservation of unknown userdata type tags.
- Binary payload preservation and metadata reporting for records such as
  hard-locked SOP `.data`: size, classification, SHA-256, and small byte
  previews.
- Take name, child-count, and observed parameter override chunks from `.takes`.
- JSON exports for records, summary, tree, individual nodes, channels, takes,
  and record diffs.
- Houdini oracle comparison for structural fields exported by
  `tools/houdini/export_oracle.py`: node paths/types/children/positions,
  connections, take names, expression channels, keyframe counts/values, and
  comparable static parameter raw values.
- Corpus-level oracle matrix reporting with committed Houdini-derived JSON
  snapshots in `tests/fixtures/oracles/`; see `docs/oracle-coverage.md`.

## Known Unknowns

- `.net` has only been observed as the `1\n` sentinel in the current corpus;
  SOP wiring is currently proven through node `.def` input blocks instead.
- Userdata type tags beyond observed type `3` are preserved but not decoded.
- Channel timing is inspectable as saved segment lengths and values, not
  converted into fully evaluated keyframe curves.
- Oracle comparison deliberately skips fields where Houdini reports UI/menu
  tokens while `.hip` stores implementation values, unless both sides are in
  the same obvious raw-value domain.
- Oracle comparison treats take ordering as non-semantic because the serialized
  `.takes` order and `hou.takes.takes()` order differ in observed fixtures.
- HDA fixtures are currently black-box metadata placeholders; real HDA
  definition parsing is not implemented.
- Binary geometry payloads are classified and preserved, not decoded.

## Fixture Rule

Fixtures are split by authority:

- `tests/fixtures/hip/generated/` contains reproducible files generated with
  `hython` using `tools/houdini/generate_fixtures.py`.
- `tests/fixtures/hip/source_truth/` contains human-authored Houdini files used
  as source-of-truth oracle cases.

Runtime package code and runtime tests must remain pure Python and must not
import `hou`.
