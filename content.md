# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-engine/src/cascade/adapters/executors/__init__.py    | 2 +-
 packages/cascade-engine/src/cascade/adapters/solvers/__init__.py | 2 +-
 packages/cascade-engine/src/cascade/adapters/state/in_memory.py  | 3 +--
 packages/cascade-engine/src/cascade/adapters/state/redis.py      | 2 +-
 packages/cascade-engine/src/cascade/runtime/flow.py              | 4 ++--
 packages/cascade-engine/src/cascade/runtime/processor.py         | 2 +-
 packages/cascade-engine/src/cascade/runtime/resolvers.py         | 2 +-
 packages/cascade-engine/src/cascade/runtime/strategies/graph.py  | 9 ++++++---
 packages/cascade-engine/src/cascade/strategies/graph.py          | 2 +-
 packages/cascade-graph/src/cascade/graph/ast_analyzer.py         | 2 +-
 tests/engine/adapters/state/test_in_memory_state.py              | 2 +-
 tests/engine/adapters/state/test_redis_state.py                  | 4 ++--
 tests/engine/graph/test_ast_analyzer.py                          | 2 +-
 tests/engine/runtime/test_flow_manager.py                        | 2 +-
 tests/engine/runtime/test_static_analysis.py                     | 2 +-
 15 files changed, 22 insertions(+), 20 deletions(-)
```