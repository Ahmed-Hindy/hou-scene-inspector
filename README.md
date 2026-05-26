# hip-reader

Early Houdini-free `.hip` scene inspection experiments.

The current reader handles Houdini `.hip` files saved by Houdini 21.0 as old
portable CPIO archives whose record names mirror the operator tree. The package
can list records, inspect global metadata, reconstruct node hierarchy, resolve
simple graph connections, parse parameters/channels/spare parameter templates,
list take overrides, preserve binary records, diff archive records, and export
JSON reports.

It does not cook or evaluate Houdini networks.

## Usage

```python
from hip_reader import HipFile

hip = HipFile.load("one_geo_with_box.hip")
print(hip.houdini_version)

for node in hip.all_nodes():
    print(node.path, node.node_type)

box = hip.node("/obj/geo1/box1")
print(box.parm("size"))
```

```powershell
uv run hip-inspect records tests/fixtures/hip/generated/one_geo_with_box.hip
uv run hip-inspect records --json tests/fixtures/hip/generated/one_geo_with_box.hip
uv run hip-inspect summary --json tests/fixtures/hip/generated/merge_two_boxes.hip
uv run hip-inspect tree tests/fixtures/hip/generated/subnet_inside_geo.hip
uv run hip-inspect node --json tests/fixtures/hip/generated/animated_translate.hip /obj/geo1/xform1
uv run hip-inspect spare-parms --json tests/fixtures/hip/generated/custom_spare_parms.hip /obj/geo1
uv run hip-inspect binary-records tests/fixtures/hip/generated/locked_geometry_or_stash.hip
uv run hip-inspect channels tests/fixtures/hip/source_truth/animation_curve_variants.hip
uv run hip-inspect takes tests/fixtures/hip/generated/two_takes_changed_parm.hip
uv run hip-inspect diff-records tests/fixtures/hip/generated/empty.hip tests/fixtures/hip/generated/one_geo_node.hip
uv run hip-inspect dump-record tests/fixtures/hip/generated/box_wired_xform.hip obj/geo1/transform1.def
```

Fixture corpora are split by authority:

- `tests/fixtures/hip/generated/` contains reproducible fixtures from
  `tools/houdini/generate_fixtures.py`.
- `tests/fixtures/hip/source_truth/` contains human-authored Houdini files used
  as source-of-truth oracle cases.

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

To compare `hip-reader` output against a Houdini API oracle:

```powershell
$oracle = "$env:TEMP\animation_curve_variants_oracle.json"
& "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" tools/houdini/export_oracle.py tests/fixtures/hip/source_truth/animation_curve_variants.hip --output $oracle --pretty
uv run hip-inspect compare-oracle tests/fixtures/hip/source_truth/animation_curve_variants.hip $oracle
```

To refresh and compare the whole fixture matrix:

```powershell
uv run hip-inspect oracle-matrix --refresh --hython "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" --write-report docs/oracle-coverage.md
```

Committed oracle snapshots live under `tests/fixtures/oracles/`, so normal
`uv run pytest` can validate the parser against Houdini-derived structural
truth without requiring Houdini at test runtime.
