# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/__init__.py               |   2 +-
 .../src/cascade/compiler/backend.py                |  46 ++++---
 .../src/cascade/compiler/exceptions.py             |   5 +-
 .../src/cascade/compiler/frontend.py               | 128 +++++++++++-------
 .../src/cascade/compiler/hashing.py                |   7 +-
 .../src/cascade/compiler/optimizer.py              |  41 +++---
 .../tests/unit/test_backend_tco.py                 | 145 ++++++++++++++-------
 .../tests/unit/test_backend_topology.py            |  90 +++++++------
 .../cascade-compiler/tests/unit/test_frontend.py   |  70 ++++++----
 .../tests/unit/test_frontend_enrichment.py         |  39 +++---
 .../cascade-compiler/tests/unit/test_optimizer.py  |  38 +++++-
 .../src/cascade/adapters/solvers/csp.py            |   5 +-
 .../src/cascade/adapters/solvers/native.py         |   4 +-
 .../cascade-engine/src/cascade/runtime/flow.py     |  45 +++++--
 .../src/cascade/runtime/processor.py               |   4 +-
 .../src/cascade/runtime/resolvers.py               |  20 ++-
 .../src/cascade/runtime/strategies/graph.py        |  30 +++--
 .../src/cascade/runtime/strategies/vm.py           |  36 ++---
 .../tests/integration/test_compiler.py             |  24 ++--
 .../integration/test_integration_map_control.py    |  27 ++--
 .../tests/integration/test_vm_linking.py           |  10 +-
 .../tests/integration/test_vm_strategy_tco.py      |  33 ++---
 .../tests/unit/test_executor_local.py              |   8 +-
 packages/cascade-graph/src/cascade/graph/build.py  |  15 ++-
 packages/cascade-graph/src/cascade/graph/model.py  |   4 +-
 .../cascade-graph/src/cascade/graph/serialize.py   |  16 +--
 packages/cascade-python/src/cascade/__init__.py    |  20 +--
 .../cascade-sdk/src/cascade/providers/__init__.py  |   2 +-
 packages/cascade-sdk/src/cascade/tools/lisp.py     |  35 +++--
 .../tests/integration/test_public_api_imports.py   |   7 +-
 ...
 74 files changed, 1083 insertions(+), 702 deletions(-)
```