# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/cascade-graph/pyproject.toml              |  22 --
 packages/cascade-graph/src/cascade/__init__.py     |  10 -
 .../cascade-graph/src/cascade/graph/__init__.py    |  14 -
 packages/cascade-graph/src/cascade/graph/build.py  | 346 ---------------------
 .../src/cascade/graph/build.stitcher.yaml          |   6 -
 .../src/cascade/graph/compiler.stitcher.yaml       |   2 -
 .../src/cascade/graph/exceptions.stitcher.yaml     |   5 -
 .../src/cascade/graph/hashing.stitcher.yaml        |  27 --
 .../src/cascade/graph/model.stitcher.yaml          |  14 -
 .../src/cascade/graph/registry.stitcher.yaml       |  10 -
 .../src/cascade/graph/serialize.stitcher.yaml      |  11 -
 packages/cascade-graph/src/cascade/py.typed        |   0
 uv.lock                                            |  28 --
 13 files changed, 495 deletions(-)
```