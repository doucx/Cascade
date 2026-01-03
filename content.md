# 📸 Snapshot Capture

### 💬 备注:
ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/backend/builder.json      |  1 +
 .../src/cascade/compiler/wiring/__init__.json      |  3 +++
 .../src/cascade/compiler/wiring/context.json       | 18 +++++++++++++++++
 .../cascade/compiler/wiring/policies/control.json  | 11 +++++++++++
 .../compiler/wiring/policies/observability.json    | 11 +++++++++++
 .../compiler/wiring/policies/parameter.json        | 11 +++++++++++
 .../cascade/compiler/wiring/policies/pulse.json    | 11 +++++++++++
 .../cascade/compiler/wiring/policies/resource.json | 20 +++++++++++++++++++
 .../src/cascade/compiler/wiring/prism.json         | 15 ++++++++++++++
 .../cascade/compiler/wiring/prisms/discrete.json   | 11 +++++++++++
 .../src/cascade/compiler/wiring/protocol.json      | 15 ++++++++++++++
 .../tests/integration/test_sovereign_wiring.json   | 15 ++++++++++++++
 .../tests/unit/test_sovereignty.json               |  6 ++++++
 .../cascade-spec/src/cascade/spec/environment.json |  3 ++-
 .../src/cascade/compiler/backend/builder.py        |  2 +-
 .../src/cascade/compiler/utils/hashing.py          |  4 +++-
 .../src/cascade/compiler/wiring/__init__.py        |  2 +-
 .../src/cascade/compiler/wiring/context.py         | 10 +++-------
 .../cascade/compiler/wiring/context.stitcher.yaml  |  3 +++
 .../cascade/compiler/wiring/policies/control.py    | 10 +++++++---
 .../compiler/wiring/policies/observability.py      |  2 +-
 .../cascade/compiler/wiring/policies/parameter.py  |  8 +++++---
 .../src/cascade/compiler/wiring/policies/pulse.py  |  2 +-
 .../cascade/compiler/wiring/policies/resource.py   |  4 ++--
 .../src/cascade/compiler/wiring/prism.py           | 18 ++---------------
 .../cascade/compiler/wiring/prism.stitcher.yaml    |  8 ++++++++
 .../src/cascade/compiler/wiring/prisms/discrete.py |  2 +-
 .../src/cascade/compiler/wiring/protocol.py        | 23 ++++------------------
 .../cascade/compiler/wiring/protocol.stitcher.yaml | 11 +++++++++++
 .../tests/integration/test_sovereign_wiring.py     | 17 ++++++----------
 ...
 32 files changed, 215 insertions(+), 71 deletions(-)
```