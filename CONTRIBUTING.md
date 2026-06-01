# Contributing

Thanks for helping improve `hou-scene-inspector`.

## Development

Use `uv` for Python environment and dependency management:

```powershell
uv sync
uv run pytest
```

The runtime package under `src/hou_scene_inspector` must remain pure Python and
must not import Houdini's `hou` module. Houdini-specific code belongs under
`tools/houdini`.

## Fixtures

Fixtures must be small, contributor-authored inspection cases. Do not commit
SideFX source code, binaries, documentation, logos, sample assets, or
proprietary production files.

When fixture or Oracle output changes are intentional, refresh and validate the
matrix:

```powershell
uv run hou-scene-inspector oracle-matrix --refresh --hython "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" --write-report docs/oracle-coverage.md --fail-on-issues
```

## Pull Requests

Before opening a pull request, run:

```powershell
uv run pytest
```

For parser or fixture changes, also run the Oracle matrix command above.
