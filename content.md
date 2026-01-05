# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-runtime/src/cascade/__init__.json      |   3 +
 .../src/cascade/runtime/__init__.json              |   3 +
 .../src/cascade/runtime/errors.json                |  22 +++++
 .../src/cascade/runtime/host/instance.json         |  54 +++++++++++
 .../src/cascade/runtime/io/cache/in_memory.json    |  17 ++++
 .../src/cascade/runtime/io/cache/redis.json        |  17 ++++
 .../src/cascade/runtime/io/caching/__init__.json   |   3 +
 .../cascade/runtime/io/caching/file_existence.json |  20 ++++
 .../src/cascade/runtime/io/executors/local.json    |  13 +++
 .../src/cascade/runtime/io/state/__init__.json     |   3 +
 .../src/cascade/runtime/io/state/in_memory.json    |  34 +++++++
 .../src/cascade/runtime/io/state/redis.json        |  44 +++++++++
 .../src/cascade/runtime/kernel/solvers/csp.json    |  16 +++
 .../src/cascade/runtime/kernel/solvers/native.json |   7 ++
 .../src/cascade/runtime/legacy/flow.json           |  40 ++++++++
 .../src/cascade/runtime/legacy/processor.json      |  44 +++++++++
 .../src/cascade/runtime/legacy/resolvers.json      |  42 ++++++++
 .../runtime/legacy/strategies/__init__.json        |   3 +
 .../cascade/runtime/legacy/strategies/base.json    |  13 +++
 .../cascade/runtime/legacy/strategies/graph.json   |  39 ++++++++
 .../src/cascade/runtime/legacy/strategies/vm.json  |  17 ++++
 .../runtime/services/constraints/__init__.json     |   3 +
 .../runtime/services/constraints/handlers.json     |  86 ++++++++++++++++
 .../runtime/services/constraints/manager.json      |  47 +++++++++
 .../runtime/services/constraints/protocols.json    |  23 +++++
 .../runtime/services/constraints/rate_limiter.json |  25 +++++
 .../runtime/services/observability/bus.json        |  27 ++++++
 .../runtime/services/observability/events.json     | 108 +++++++++++++++++++++
 .../services/observability/subscribers.json        |  73 ++++++++++++++
 .../runtime/services/resources/container.json      |  50 ++++++++++
 ...
 58 files changed, 1391 insertions(+), 2 deletions(-)
```