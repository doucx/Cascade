# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/backend/builder.json      |  7 ++++--
 .../src/cascade/compiler/backend/expander.json     | 11 +++++++++-
 .../compiler/backend/expansion/context.json        |  8 +++++++
 .../backend/expansion/policies/control.json        |  7 ++++++
 .../backend/expansion/policies/parameter.json      |  7 ++++++
 .../compiler/backend/expansion/policies/pulse.json |  7 ++++++
 .../backend/expansion/policies/resource.json       | 16 ++++++++++++++
 .../compiler/backend/expansion/protocol.json       | 10 +++++++++
 .../cascade/compiler/backend/wiring/harness.json   |  9 +++++++-
 .../src/cascade/compiler/backend/wiring/prism.json | 12 ++++++++++-
 .../compiler/backend/wiring/prisms/discrete.json   |  8 +++++++
 .../src/cascade/compiler/backend/builder.py        | 14 +-----------
 .../cascade/compiler/backend/builder.stitcher.yaml |  8 +++----
 .../src/cascade/compiler/backend/expander.py       |  2 +-
 .../compiler/backend/expander.stitcher.yaml        |  6 +++---
 .../cascade/compiler/backend/expansion/context.py  |  2 +-
 .../compiler/backend/expansion/policies/control.py |  6 ++----
 .../backend/expansion/policies/parameter.py        |  2 +-
 .../compiler/backend/expansion/policies/pulse.py   |  2 +-
 .../backend/expansion/policies/resource.py         |  4 ++--
 .../cascade/compiler/backend/expansion/protocol.py | 11 +---------
 .../backend/expansion/protocol.stitcher.yaml       | 20 ++++++-----------
 .../src/cascade/compiler/backend/wiring/harness.py |  1 -
 .../compiler/backend/wiring/harness.stitcher.yaml  |  2 ++
 .../compiler/backend/wiring/policies/control.py    |  2 +-
 .../compiler/backend/wiring/policies/parameter.py  |  2 +-
 .../compiler/backend/wiring/policies/pulse.py      |  2 +-
 .../compiler/backend/wiring/policies/resource.py   |  2 +-
 .../src/cascade/compiler/backend/wiring/prism.py   | 25 +++-------------------
 .../compiler/backend/wiring/prism.stitcher.yaml    |  4 ++--
 ...
 31 files changed, 133 insertions(+), 88 deletions(-)
```