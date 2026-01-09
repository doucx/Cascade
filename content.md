# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/spec/physics/__init__.json         |  3 +
 .../src/cascade/spec/physics/core.json             | 55 ++++++++++++++
 .../src/cascade/spec/physics/spec.json             | 14 ++++
 .../cascade-std/src/cascade/std/kernel_tools.json  | 56 +++++++++++++++
 .../src/cascade/std/resource/discrete.json         |  8 +--
 .../src/cascade/std/resource/requestor.json        |  4 +-
 .../src/cascade/std/specs/__init__.json            |  3 +
 .../src/cascade/std/specs/resource.json            | 23 ++++++
 .../cascade-std/src/cascade/std/specs/system.json  | 17 +++++
 .../cascade-std/src/cascade/std/specs/triad.json   | 30 ++++++++
 .../cascade-std/src/cascade/std/system/egress.json |  4 +-
 .../cascade-std/src/cascade/std/system/gate.json   |  4 +-
 .../src/cascade/std/triad/bleacher.json            |  4 +-
 .../src/cascade/compiler/backend/expander.py       |  4 +-
 .../compiler/backend/wiring/policies/control.py    | 22 ++++--
 .../backend/wiring/policies/observability.py       | 14 ++--
 .../compiler/backend/wiring/policies/parameter.py  |  5 +-
 .../compiler/backend/wiring/policies/pulse.py      |  4 +-
 .../compiler/backend/wiring/prisms/discrete.py     | 10 ++-
 .../src/cascade/spec/physics/__init__.py           |  2 +-
 .../cascade-spec/src/cascade/spec/physics/core.py  | 48 +++++--------
 .../src/cascade/spec/physics/core.stitcher.yaml    | 16 +++++
 .../cascade-spec/src/cascade/spec/physics/spec.py  | 25 +++----
 .../src/cascade/spec/physics/spec.stitcher.yaml    |  8 +++
 .../cascade-std/src/cascade/std/kernel_tools.py    | 84 ++++++++++------------
 .../src/cascade/std/kernel_tools.stitcher.yaml     | 10 +++
 .../cascade-std/src/cascade/std/specs/__init__.py  |  8 ++-
 .../cascade-std/src/cascade/std/specs/resource.py  | 20 ++----
 .../src/cascade/std/specs/resource.stitcher.yaml   |  9 +++
 .../cascade-std/src/cascade/std/specs/system.py    | 15 +---
 ...
 36 files changed, 402 insertions(+), 183 deletions(-)
```