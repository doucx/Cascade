# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../tests/integration/test_app_tools.json           |  9 ++++++---
 .../tests/integration/test_controller_app.json      | 12 ++++++++----
 .../tests/integration/test_controller_cli.json      |  3 ++-
 .../tests/integration/test_telemetry_contract.json  |  3 ++-
 .../tests/unit/test_observer_app.json               | 18 ++++++++++++------
 .../cascade-common/src/cascade/common/context.json  | 21 +++++++++++++++++++++
 .../cascade-common/src/cascade/common/inputs.json   |  3 ++-
 .../cascade-common/tests/unit/test_messaging.json   |  6 ++++--
 .../tests/integration/test_local_connector.json     | 12 ++++++++----
 .../cascade-connector-mqtt/tests/unit/conftest.json |  3 ++-
 .../tests/unit/test_connector.json                  | 15 ++++++++++-----
 .../cascade-engine/src/cascade/runtime/engine.json  |  4 ++--
 .../src/cascade/runtime/processor.json              |  4 ++--
 .../tests/integration/test_engine_concurrency.json  |  6 ++++--
 .../tests/integration/test_engine_constraints.json  | 21 ++++++++++++++-------
 .../tests/integration/test_engine_control_flow.json |  3 ++-
 .../tests/integration/test_engine_core.json         |  3 ++-
 .../test_engine_explicit_control_flow.json          |  3 ++-
 .../tests/integration/test_engine_inputs.json       |  6 ++++--
 .../tests/integration/test_engine_map.json          | 15 ++++++++++-----
 .../tests/integration/test_engine_map_policies.json |  6 ++++--
 .../tests/integration/test_engine_map_reduce.json   |  3 ++-
 .../tests/integration/test_engine_retry.json        |  6 ++++--
 .../integration/test_engine_router_pruning.json     |  6 ++++--
 .../integration/test_file_existence_cache.json      |  6 ++++--
 .../cascade-engine/tests/unit/test_bus.json         | 12 ++++++++----
 .../tests/unit/test_cache_in_memory.json            | 15 ++++++++++-----
 .../cascade-engine/tests/unit/test_cache_redis.json | 12 ++++++++----
 .../tests/unit/test_executor_local.json             |  6 ++++--
 .../tests/unit/test_flow_manager.json               |  9 ++++++---
 ...
 64 files changed, 440 insertions(+), 190 deletions(-)
```