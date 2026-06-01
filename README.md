# hou-scene-inspector

`.hip scene-structure inspection`.

The current reader handles Houdini `.hip` files saved by Houdini 21.0 as old
portable CPIO archives whose record names mirror the operator tree. The package
can list records, inspect global metadata, reconstruct node hierarchy, resolve
simple graph connections, parse parameters/channels/spare parameter templates,
list take overrides, preserve binary records, diff archive records, and export
JSON reports.

It does not cook or evaluate Houdini networks.

## Install

```powershell
uv tool install git+https://github.com/Ahmed-Hindy/hou-scene-inspector
```

For local development, clone the repository and run:

```powershell
uv sync
uv run pytest
```

## Legal / Scope Note

This is an independent, unofficial project for inspecting user-created `.hip`
scene structure. It is not affiliated with, endorsed by, sponsored by, or
supported by SideFX. Houdini and SideFX are trademarks of Side Effects Software
Inc.; those names are used here only to identify file compatibility context.

This repository does not include SideFX source code, binaries, documentation,
logos, sample assets, or proprietary production files. It must not be used to
bypass license, commercial/non-commercial, security, watermarking, entitlement,
or usage restrictions.

## Usage

```python
from hou_scene_inspector import HipFile

hip = HipFile.load("one_geo_with_box.hip")
print(hip.houdini_version)

for node in hip.all_nodes():
    print(node.path, node.node_type)

box = hip.node("/obj/geo1/box1")
print(box.parm("size"))
```

```powershell
uv run hou-scene-inspector records tests/fixtures/hip/generated/one_geo_with_box.hip
uv run hou-scene-inspector records --json tests/fixtures/hip/generated/one_geo_with_box.hip
uv run hou-scene-inspector summary --json tests/fixtures/hip/generated/merge_two_boxes.hip
uv run hou-scene-inspector tree tests/fixtures/hip/generated/subnet_inside_geo.hip
uv run hou-scene-inspector node --json tests/fixtures/hip/generated/animated_translate.hip /obj/geo1/xform1
uv run hou-scene-inspector spare-parms --json tests/fixtures/hip/generated/custom_spare_parms.hip /obj/geo1
uv run hou-scene-inspector binary-records tests/fixtures/hip/generated/locked_geometry_or_stash.hip
uv run hou-scene-inspector channels tests/fixtures/hip/source_truth/animation_curve_variants.hip
uv run hou-scene-inspector takes tests/fixtures/hip/generated/two_takes_changed_parm.hip
uv run hou-scene-inspector diff-records tests/fixtures/hip/generated/empty.hip tests/fixtures/hip/generated/one_geo_node.hip
uv run hou-scene-inspector dump-record tests/fixtures/hip/generated/box_wired_xform.hip obj/geo1/transform1.def
```

Fixture corpora are split by authority:

- `tests/fixtures/hip/generated/` contains reproducible fixtures from
  `tools/houdini/generate_fixtures.py`.
- `tests/fixtures/hip/source_truth/` contains human-authored Houdini files used
  as contributor-authored inspection cases for Oracle comparison.

See [docs/compatibility.md](docs/compatibility.md) for the current supported
surface and known unknowns.

## Development

```powershell
uv sync
uv run pytest
```

To regenerate the controlled fixture corpus with Houdini 21.0:

```powershell
& "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" tools/houdini/generate_fixtures.py
```

To compare `hou-scene-inspector` output against an Oracle:

```powershell
$oracle = "$env:TEMP\animation_curve_variants_oracle.json"
& "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" tools/houdini/export_oracle.py tests/fixtures/hip/source_truth/animation_curve_variants.hip --output $oracle --pretty
uv run hou-scene-inspector compare-oracle tests/fixtures/hip/source_truth/animation_curve_variants.hip $oracle
```

To refresh and compare the whole fixture matrix:

```powershell
uv run hou-scene-inspector oracle-matrix --refresh --hython "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" --write-report docs/oracle-coverage.md
```

Committed Oracle snapshots live under `tests/fixtures/oracles/`, so normal
`uv run pytest` can validate the parser against structural truth without
requiring Houdini at test runtime.

## License

`hou-scene-inspector` is released under the MIT License. See
[LICENSE](LICENSE).
