# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
observatory/benchmarks/tco_performance.py               | 14 +++++++++-----
 .../src/cascade/adapters/executors/local.py             |  3 ---
 .../cascade-engine/src/cascade/adapters/solvers/csp.py  |  4 +---
 packages/cascade-engine/src/cascade/runtime/events.py   |  1 +
 .../cascade-engine/src/cascade/runtime/processor.py     |  2 +-
 .../cascade-engine/src/cascade/runtime/resolvers.py     | 17 ++++++++++-------
 .../src/cascade/runtime/strategies/graph.py             | 14 +++++++++-----
 packages/cascade-graph/src/cascade/graph/build.py       |  3 ---
 packages/cascade-graph/src/cascade/graph/exceptions.py  |  2 +-
 packages/cascade-graph/src/cascade/graph/hashing.py     |  6 ++----
 packages/cascade-graph/src/cascade/graph/model.py       |  2 --
 packages/cascade-sdk/src/cascade/control_flow.py        |  2 +-
 packages/cascade-sdk/src/cascade/tools/visualize.py     |  4 +---
 packages/cascade-spec/src/cascade/spec/jump.py          |  2 +-
 tests/engine/graph/test_static_integrity.py             |  6 ++----
 tests/engine/integration/test_plan_caching.py           |  2 +-
 tests/engine/runtime/test_explicit_control_flow.py      |  2 +-
 tests/sdk/tools/test_visualize.py                       |  9 ++-------
 18 files changed, 43 insertions(+), 52 deletions(-)
```