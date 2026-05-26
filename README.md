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
uv run hip-inspect records tests/fixtures/hip/one_geo_with_box.hip
uv run hip-inspect records --json tests/fixtures/hip/one_geo_with_box.hip
uv run hip-inspect summary --json tests/fixtures/hip/merge_two_boxes.hip
uv run hip-inspect tree tests/fixtures/hip/subnet_inside_geo.hip
uv run hip-inspect node --json tests/fixtures/hip/animated_translate.hip /obj/geo1/xform1
uv run hip-inspect channels tests/fixtures/hip/animated_translate.hip
uv run hip-inspect takes tests/fixtures/hip/two_takes_changed_parm.hip
uv run hip-inspect diff-records tests/fixtures/hip/empty.hip tests/fixtures/hip/one_geo_node.hip
uv run hip-inspect dump-record tests/fixtures/hip/box_wired_xform.hip obj/geo1/transform1.def
```

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
