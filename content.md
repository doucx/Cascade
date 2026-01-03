# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/app/__init__.py                    |  6 +--
 .../src/cascade/compiler/backend/builder.py        |  2 +-
 .../src/cascade/compiler/backend/expander.py       |  2 +-
 .../src/cascade/compiler/frontend/generator.py     |  2 +-
 .../src/cascade/compiler/utils/hashing.py          |  6 +--
 .../cascade/compiler/wiring/policies/control.py    |  4 +-
 .../cascade/compiler/wiring/policies/parameter.py  |  6 +--
 .../src/cascade/compiler/wiring/policies/pulse.py  |  4 +-
 .../cascade/compiler/wiring/policies/resource.py   |  2 +-
 .../src/cascade/compiler/wiring/prisms/discrete.py |  8 ++--
 .../tests/unit/backend/test_builder.py             |  6 +--
 .../tests/unit/backend/test_builder_environment.py |  2 +-
 .../tests/unit/backend/test_expander.py            |  2 +-
 .../tests/unit/test_sovereignty.py                 |  2 +-
 .../src/cascade/adapters/solvers/csp.py            |  8 ++--
 .../src/cascade/adapters/solvers/native.py         | 24 +++++------
 .../cascade-engine/src/cascade/runtime/flow.py     | 46 ++++++++++----------
 .../src/cascade/runtime/processor.py               | 22 +++++-----
 .../src/cascade/runtime/resolvers.py               | 26 +++++------
 .../src/cascade/runtime/strategies/graph.py        | 42 +++++++++---------
 .../tests/unit/test_executor_local.py              |  4 +-
 .../cascade-engine/tests/unit/test_flow_manager.py |  4 +-
 packages/cascade-graph/src/cascade/graph/build.py  |  6 +--
 .../cascade-graph/src/cascade/graph/hashing.py     | 10 ++---
 packages/cascade-graph/src/cascade/graph/model.py  | 10 ++---
 .../cascade-graph/src/cascade/graph/serialize.py   | 14 +++---
 packages/cascade-graph/tests/unit/test_hashing.py  |  2 +-
 .../cascade-graph/tests/unit/test_purity_model.py  |  4 +-
 packages/cascade-sdk/src/cascade/tools/lisp.py     | 50 +++++++++++-----------
 .../tests/integration/test_state_backends.py       |  2 +-
 ...
 34 files changed, 179 insertions(+), 179 deletions(-)
```