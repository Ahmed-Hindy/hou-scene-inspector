# hip-reader

Early Houdini-free `.hip` scene inspection experiments.

The current reader handles the first useful layer of the format: Houdini `.hip`
files saved by Houdini 21.0 are old portable CPIO archives whose record names
mirror the operator tree. The package can list records, inspect global scene
metadata, reconstruct a node hierarchy, and read node definitions, child order,
simple SOP input/output connections, parameters, spare parameter template names,
channel text, and observed string userdata.

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
uv run hip-inspect records one_geo_with_box.hip
uv run hip-inspect summary one_geo_with_box.hip
uv run hip-inspect tree one_geo_with_box.hip
```

## Development

```powershell
uv sync
uv run pytest
```
