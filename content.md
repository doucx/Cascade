# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/__init__.json             |  3 ++
 .../src/cascade/spec/compiler/interfaces.json      | 29 ++++++++++
 .../src/cascade/spec/compiler/model.json           | 13 +++++
 .../src/cascade/spec/vm/interfaces.json            | 28 ++++++++++
 .../src/cascade/test_utils/__init__.json           |  3 ++
 .../src/cascade/test_utils/harness.json            | 62 ++++++++++++++++++++++
 .../src/cascade/compiler/__init__.py               |  2 +-
 .../src/cascade/compiler/backend/expander.py       |  3 +-
 .../compiler/backend/expander.stitcher.yaml        | 14 -----
 .../cascade/compiler/backend/expansion/protocol.py |  1 -
 .../backend/expansion/protocol.stitcher.yaml       | 11 ----
 .../cascade/compiler/backend/wiring/protocol.py    |  1 -
 .../compiler/backend/wiring/protocol.stitcher.yaml | 11 ----
 .../src/cascade/runtime/__init__.py                |  2 +-
 .../src/cascade/spec/compiler/interfaces.py        | 15 ++++--
 .../src/cascade/spec/compiler/model.py             |  7 +--
 .../src/cascade/spec/compiler/model.stitcher.yaml  |  3 ++
 .../cascade-spec/src/cascade/spec/vm/interfaces.py |  4 +-
 .../src/cascade/test_utils/__init__.py             |  2 +-
 .../src/cascade/test_utils/harness.py              |  2 +-
 packages/cascade-vm/src/cascade/vm/protocols.py    |  1 -
 .../src/cascade/vm/protocols.stitcher.yaml         |  8 ---
 22 files changed, 161 insertions(+), 64 deletions(-)
```