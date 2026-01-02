# 📸 Snapshot Capture

### 💬 备注:
stitcher doc

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/utils/naming.json         | 45 ++++++++++++++++++++++
 .../integration/test_observability_congestion.json | 16 ++++++++
 .../cascade-spec/src/cascade/spec/physics.json     |  7 +++-
 .../cascade-spec/src/cascade/spec/ports.json       | 11 ++++++
 .../src/cascade/vm/instructions/bleacher.json      |  4 +-
 .../src/cascade/vm/instructions/stainer.json       |  4 +-
 .../tests/unit/instructions/test_bleacher.json     |  4 ++
 .../tests/unit/instructions/test_stainer.json      |  4 ++
 .../src/cascade/compiler/backend/expander.py       |  2 +-
 .../src/cascade/compiler/utils/naming.py           |  4 --
 .../cascade/compiler/utils/naming.stitcher.yaml    |  3 ++
 .../integration/test_observability_congestion.py   |  6 ---
 .../test_observability_congestion.stitcher.yaml    |  4 ++
 .../src/cascade/spec/physics.stitcher.yaml         |  6 ++-
 packages/cascade-spec/src/cascade/spec/ports.py    |  2 +-
 .../src/cascade/vm/instructions/bleacher.py        |  4 +-
 .../src/cascade/vm/instructions/stainer.py         |  4 +-
 .../integration/test_resource_backpressure.py      |  1 -
 .../tests/unit/instructions/test_bleacher.py       |  8 +---
 19 files changed, 106 insertions(+), 33 deletions(-)
```