# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/app/__init__.py                    |  6 +--
 .../src/cascade/compiler/analysis/reflection.py    |  2 +-
 .../src/cascade/compiler/backend.py                | 18 ++++----
 .../src/cascade/compiler/frontend.py               | 30 ++++++-------
 .../src/cascade/compiler/hashing.py                | 10 ++---
 .../src/cascade/compiler/optimizer.py              |  8 ++--
 .../cascade-compiler/tests/unit/test_backend.py    | 20 ++++-----
 .../tests/unit/test_backend_enrichment.py          |  4 +-
 .../tests/unit/test_compiler_linking.py            |  4 +-
 .../cascade-compiler/tests/unit/test_frontend.py   |  4 +-
 .../cascade-compiler/tests/unit/test_optimizer.py  | 14 +++---
 .../src/cascade/adapters/solvers/csp.py            |  8 ++--
 .../src/cascade/adapters/solvers/native.py         | 24 +++++------
 .../cascade-engine/src/cascade/runtime/flow.py     | 46 ++++++++++----------
 .../src/cascade/runtime/processor.py               | 22 +++++-----
 .../src/cascade/runtime/resolvers.py               | 26 +++++------
 .../src/cascade/runtime/strategies/graph.py        | 42 +++++++++---------
 .../tests/unit/test_executor_local.py              |  4 +-
 .../cascade-engine/tests/unit/test_flow_manager.py |  4 +-
 packages/cascade-graph/src/cascade/graph/build.py  |  6 +--
 packages/cascade-graph/src/cascade/graph/model.py  | 10 ++---
 .../cascade-graph/src/cascade/graph/serialize.py   | 14 +++---
 packages/cascade-graph/tests/unit/test_hashing.py  |  2 +-
 .../cascade-graph/tests/unit/test_purity_model.py  |  4 +-
 packages/cascade-sdk/src/cascade/tools/lisp.py     | 50 +++++++++++-----------
 .../tests/integration/test_state_backends.py       |  2 +-
 packages/cascade-sdk/tests/unit/test_visualize.py  | 20 ++++-----
 .../cascade-spec/src/cascade/spec/blueprint.py     |  4 +-
 .../cascade-spec/src/cascade/spec/ir/models.py     |  6 +--
 .../tests/blueprint/test_instruction_policy.py     |  2 +-
 ...
 40 files changed, 239 insertions(+), 239 deletions(-)
```