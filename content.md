# 📸 Snapshot Capture

### 💬 备注:
ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/adapters/executors/local.json         |  4 ++--
 .../cascade-engine/src/cascade/runtime/processor.json | 12 ++++++------
 .../cascade-engine/src/cascade/runtime/resolvers.json |  8 ++++++--
 .../src/cascade/runtime/resource_container.json       |  4 ++--
 .../src/cascade/runtime/strategies/graph.json         |  8 ++++++--
 .../cascade-graph/src/cascade/graph/build.json        |  9 +++++----
 .../cascade-graph/src/cascade/graph/serialize.json    | 12 ++++++------
 .../packages/cascade-sdk/src/cascade/testing.json     | 19 +++++++++++++++----
 .../cascade-engine/src/cascade/runtime/processor.py   |  4 ++--
 .../src/cascade/runtime/strategies/graph.py           |  6 ++++--
 .../tests/integration/test_engine_concurrency.py      |  1 -
 packages/cascade-graph/src/cascade/graph/build.py     |  2 +-
 packages/cascade-graph/src/cascade/graph/model.py     |  2 +-
 packages/cascade-sdk/src/cascade/testing.py           |  4 +---
 tests/e2e/runtime/test_e2e_local_connector.py         |  1 -
 15 files changed, 57 insertions(+), 39 deletions(-)
```