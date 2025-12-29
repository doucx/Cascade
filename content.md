# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/app/__init__.json                  |  6 +-
 .../src/cascade/connectors/local/connector.json    |  4 +-
 .../src/cascade/connectors/mqtt/connector.json     | 12 +++-
 .../src/cascade/adapters/cache/redis.json          |  4 +-
 .../src/cascade/adapters/state/redis.json          |  4 +-
 .../cascade/runtime/constraints/rate_limiter.json  |  4 +-
 .../cascade-engine/src/cascade/runtime/engine.json |  4 +-
 .../cascade-engine/src/cascade/runtime/events.json | 12 ++++
 .../src/cascade/runtime/processor.json             |  8 +--
 .../src/cascade/runtime/resolvers.json             |  8 +--
 .../src/cascade/runtime/strategies/graph.json      |  4 +-
 .../cascade-engine/src/cascade/runtime/vm.json     |  4 +-
 .../src/cascade/providers/helpers.json             |  2 +-
 .../cascade-library/src/cascade/providers/sql.json |  4 +-
 .../src/cascade/providers/stdio.json               |  2 +-
 .../src/cascade/providers/ipfs/provider.json       |  8 +--
 .../cascade-sdk/src/cascade/internal/inputs.json   |  2 +-
 .../cascade-sdk/src/cascade/providers/manager.json | 26 ++++++++
 .../src/cascade/providers/registry.json            | 70 +++-------------------
 .../packages/cascade-sdk/src/cascade/testing.json  | 16 +++--
 .../cascade-sdk/src/cascade/tools/events.json      | 28 ++-------
 .../cascade-spec/src/cascade/spec/lazy_types.json  | 40 +++++++++++++
 .../cascade-spec/src/cascade/spec/protocols.json   |  8 +++
 .../cascade-spec/src/cascade/spec/resource.json    |  4 +-
 .../cascade-spec/src/cascade/spec/task.json        | 34 +----------
 .../src/cascade/app/__init__.stitcher.yaml         |  2 -
 .../src/cascade/providers/registry.stitcher.yaml   | 19 ------
 .../src/cascade/tools/events.stitcher.yaml         |  8 ---
 .../src/cascade/spec/task.stitcher.yaml            |  3 -
 29 files changed, 159 insertions(+), 191 deletions(-)
```