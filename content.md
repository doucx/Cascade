# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
observatory/benchmarks/tco_performance.py          |  10 +-
 .../src/cascade/adapters/solvers/native.py         |   4 +-
 .../src/cascade/adapters/state/in_memory.py        |   5 -
 .../cascade-engine/src/cascade/runtime/flow.py     |   4 +-
 .../src/cascade/runtime/processor.py               |   6 +-
 .../src/cascade/runtime/resolvers.py               |  82 ++++++++---
 .../src/cascade/runtime/resource_container.py      |  14 +-
 .../src/cascade/runtime/strategies/__init__.py     |   2 +-
 .../src/cascade/runtime/strategies/base.py         |   2 +-
 .../src/cascade/runtime/strategies/graph.py        |  26 ++--
 .../src/cascade/runtime/strategies/vm.py           |   4 +-
 .../cascade-graph/src/cascade/graph/__init__.py    |   2 +-
 .../src/cascade/graph/ast_analyzer.py              |  10 +-
 packages/cascade-graph/src/cascade/graph/build.py  | 164 ++++++++++++++++-----
 packages/cascade-graph/src/cascade/graph/model.py  |   7 +-
 .../cascade-graph/src/cascade/graph/registry.py    |  10 +-
 .../cascade-graph/src/cascade/graph/serialize.py   |   2 +-
 .../cascade-sdk/src/cascade/tools/visualize.py     |   1 -
 packages/cascade-spec/src/cascade/spec/binding.py  |   2 +-
 tests/engine/graph/test_build_tco.py               |  10 +-
 tests/engine/graph/test_hashing.py                 |   4 +-
 tests/engine/runtime/test_flow_manager.py          |   2 +-
 .../engine/runtime/test_jit_cache_verification.py  |  19 ++-
 tests/engine/runtime/test_tco_cache.py             |   3 +-
 tests/engine/runtime/test_tco_mutual_recursion.py  |  12 +-
 tests/sdk/integration/test_state_backends.py       |   4 +-
 tests/sdk/tools/test_visualize.py                  |   8 +-
 27 files changed, 283 insertions(+), 136 deletions(-)
```