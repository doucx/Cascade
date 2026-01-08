# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade/compiler/backend/wiring/__init__.json  |  3 +
 .../cascade/compiler/backend/wiring/context.json   | 18 +++++
 .../compiler/backend/wiring/policies/control.json  | 11 +++
 .../backend/wiring/policies/observability.json     | 11 +++
 .../backend/wiring/policies/parameter.json         | 11 +++
 .../compiler/backend/wiring/policies/pulse.json    | 11 +++
 .../compiler/backend/wiring/policies/resource.json | 20 ++++++
 .../src/cascade/compiler/backend/wiring/prism.json | 15 +++++
 .../compiler/backend/wiring/prisms/discrete.json   | 11 +++
 .../cascade/compiler/backend/wiring/protocol.json  | 15 +++++
 .../src/cascade/compiler/wiring/__init__.json      |  3 -
 .../src/cascade/compiler/wiring/context.json       | 18 -----
 .../cascade/compiler/wiring/policies/control.json  | 11 ---
 .../compiler/wiring/policies/observability.json    | 11 ---
 .../compiler/wiring/policies/parameter.json        | 11 ---
 .../cascade/compiler/wiring/policies/pulse.json    | 11 ---
 .../cascade/compiler/wiring/policies/resource.json | 20 ------
 .../src/cascade/compiler/wiring/prism.json         | 15 -----
 .../cascade/compiler/wiring/prisms/discrete.json   | 11 ---
 .../src/cascade/compiler/wiring/protocol.json      | 15 -----
 .../src/cascade/compiler/backend/builder.py        | 14 ++--
 .../src/cascade/compiler/backend/wiring.py         | 78 ----------------------
 .../cascade/compiler/backend/wiring.stitcher.yaml  | 11 ---
 .../cascade/compiler/backend/wiring/__init__.py    |  0
 .../src/cascade/compiler/backend/wiring/context.py | 26 ++++++++
 .../compiler/backend/wiring/context.stitcher.yaml  |  3 +
 .../src/cascade/compiler/backend/wiring/harness.py | 78 ++++++++++++++++++++++
 .../compiler/backend/wiring/harness.stitcher.yaml  | 11 +++
 .../compiler/backend/wiring/policies/__init__.py   |  0
 .../compiler/backend/wiring/policies/control.py    | 60 +++++++++++++++++
 ...
 55 files changed, 754 insertions(+), 758 deletions(-)
```