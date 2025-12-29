# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/runtime/strategies/graph.py        |  10 +-
 packages/cascade-engine/src/cascade/runtime/vm.py  |   4 +-
 .../tests/adapters/executors/test_local.py         |   5 +-
 .../src/cascade/graph/analysis/__init__.py         |   2 +-
 .../src/cascade/graph/analysis/protocols.py        |   2 +-
 .../src/cascade/graph/analysis/reflection.py       |  46 ++++---
 packages/cascade-graph/src/cascade/graph/build.py  | 141 ++++++++++++++++-----
 .../cascade-graph/src/cascade/graph/hashing.py     |  42 +++---
 packages/cascade-graph/src/cascade/graph/model.py  |  10 +-
 .../cascade-graph/src/cascade/graph/serialize.py   |   7 +-
 packages/cascade-sdk/src/cascade/__init__.py       |  16 +--
 packages/cascade-sdk/src/cascade/testing.py        |  24 ++--
 packages/cascade-spec/src/cascade/spec/__init__.py |   2 +-
 .../cascade-spec/src/cascade/spec/fingerprint.py   |   2 +-
 .../cascade-spec/src/cascade/spec/ir/__init__.py   |   2 +-
 .../cascade-spec/src/cascade/spec/ir/models.py     |   9 +-
 tests/e2e/runtime/harness.py                       |   5 +-
 tests/e2e/runtime/test_e2e_concurrency_control.py  |  54 ++++----
 18 files changed, 238 insertions(+), 145 deletions(-)
```