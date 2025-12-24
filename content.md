# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/adapters/solvers/csp.py            | 12 ++++++--
 .../src/cascade/adapters/solvers/native.py         | 21 +++++++++++---
 .../cascade-engine/src/cascade/runtime/flow.py     | 20 +++++++++----
 .../src/cascade/runtime/processor.py               | 22 +++++++++++----
 .../src/cascade/runtime/resolvers.py               | 33 +++++++++++++++++-----
 .../src/cascade/runtime/strategies/graph.py        |  8 ++++--
 packages/cascade-engine/src/cascade/runtime/vm.py  |  3 +-
 packages/cascade-graph/src/cascade/graph/build.py  |  2 +-
 .../cascade-graph/src/cascade/graph/hashing.py     | 32 ++++++++++++---------
 .../cascade-graph/src/cascade/graph/serialize.py   |  3 +-
 packages/cascade-sdk/src/cascade/tools/lisp.py     | 17 ++++++++---
 .../cascade-sdk/src/cascade/tools/visualize.py     |  4 ++-
 tests/engine/adapters/executors/test_local.py      |  4 ++-
 tests/sdk/tools/test_visualize.py                  | 15 ++++++++--
 14 files changed, 144 insertions(+), 52 deletions(-)
```