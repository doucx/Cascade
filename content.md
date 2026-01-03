# 📸 Snapshot Capture

### 💬 备注:
ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-graph/src/cascade/graph/model.json     |  1 +
 .../cascade-spec/src/cascade/spec/ir/models.json   |  1 +
 .../src/cascade/compiler/utils/hashing.py          | 12 ++++--
 .../cascade/compiler/wiring/policies/control.py    |  4 +-
 .../cascade/compiler/wiring/policies/parameter.py  |  8 +++-
 .../src/cascade/compiler/wiring/policies/pulse.py  |  4 +-
 .../src/cascade/compiler/wiring/prisms/discrete.py | 12 ++++--
 .../tests/unit/backend/test_builder.py             |  4 +-
 .../tests/unit/backend/test_builder_environment.py |  7 +++-
 .../tests/unit/frontend/test_generator.py          |  5 ++-
 .../tests/unit/test_sovereignty.py                 |  4 +-
 .../src/cascade/adapters/solvers/csp.py            |  5 ++-
 .../src/cascade/adapters/solvers/native.py         |  4 +-
 .../cascade-engine/src/cascade/runtime/flow.py     | 45 +++++++++++++++-------
 .../src/cascade/runtime/processor.py               |  4 +-
 .../src/cascade/runtime/resolvers.py               | 20 ++++++++--
 .../src/cascade/runtime/strategies/graph.py        | 30 +++++++++++----
 .../tests/unit/test_executor_local.py              |  8 +++-
 .../cascade-graph/src/cascade/graph/hashing.py     |  7 +++-
 packages/cascade-sdk/src/cascade/tools/lisp.py     | 25 +++++++++---
 packages/cascade-sdk/tests/unit/test_visualize.py  | 10 ++++-
 .../integration/test_source_node_execution.py      |  4 +-
 scripts/refactor_hash_ids.py                       | 10 +++--
 23 files changed, 176 insertions(+), 58 deletions(-)
```