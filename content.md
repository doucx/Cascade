# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/reflection/naming.json                  |  4 ++++
 .../cascade-spec/src/cascade/spec/physical/triad.json   |  2 ++
 .../cascade-std/src/cascade/std/system/retry.json       |  7 +++++++
 .../tests/integration/test_retry_topology.json          | 17 +++++++++++++++++
 .../src/cascade/compiler/backend/expander.py            |  1 -
 packages/cascade-spec/src/cascade/spec/__init__.py      |  1 +
 packages/cascade-std/src/cascade/std/system/retry.py    | 13 +------------
 .../src/cascade/std/system/retry.stitcher.yaml          | 10 ++++++++++
 packages/cascade-vm/src/cascade/vm/linker.py            |  1 -
 .../cascade-vm/tests/integration/test_retry_topology.py | 12 ------------
 .../tests/integration/test_retry_topology.stitcher.yaml |  9 +++++++++
 11 files changed, 51 insertions(+), 26 deletions(-)
```