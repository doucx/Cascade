# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/app/__init__.json                  |  4 ++--
 .../src/cascade/cli/controller/app.json            |  6 +++---
 .../src/cascade/cli/observer/app.json              |  4 ++--
 .../src/cascade/cli/observer/rendering.json        |  4 ++--
 .../src/cascade/common/messaging/bus.json          | 12 +++++------
 .../src/cascade/common/messaging/protocols.json    |  2 +-
 .../src/cascade/common/renderers.json              |  8 ++++----
 .../src/cascade/connectors/local/bus.json          |  2 +-
 .../src/cascade/connectors/local/connector.json    |  6 +++---
 .../src/cascade/connectors/mqtt/connector.json     |  2 +-
 .../src/cascade/adapters/cache/redis.json          |  2 +-
 .../src/cascade/adapters/state/redis.json          |  2 +-
 .../src/cascade/runtime/constraints/handlers.json  | 24 +++++++++++-----------
 .../src/cascade/runtime/constraints/protocols.json |  8 ++++----
 .../src/cascade/runtime/exceptions.json            |  2 +-
 .../cascade-graph/src/cascade/graph/build.json     |  2 +-
 .../src/cascade/providers/helpers.json             |  4 ++--
 .../src/cascade/providers/http.json                |  4 ++--
 .../cascade-library/src/cascade/providers/io.json  |  4 ++--
 .../cascade-library/src/cascade/providers/s3.json  |  4 ++--
 .../src/cascade/providers/signal.json              |  2 +-
 .../src/cascade/providers/stdio.json               |  2 +-
 .../src/cascade/providers/template.json            |  2 +-
 .../src/cascade/providers/ipfs/cache.json          |  2 +-
 .../src/cascade/providers/ipfs/provider.json       |  4 ++--
 .../packages/cascade-sdk/src/cascade/__init__.json |  6 +++---
 .../src/cascade/examples/patterns/llm_openai.json  |  2 +-
 .../cascade-sdk/src/cascade/internal/inputs.json   |  2 +-
 .../src/cascade/providers/registry.json            |  6 +++---
 .../packages/cascade-sdk/src/cascade/testing.json  |  4 ++--
 ...
 36 files changed, 84 insertions(+), 84 deletions(-)
```