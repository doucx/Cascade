# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../tests/integration/test_app_tools.json          | 14 ++++++++
 .../tests/integration/test_controller_app.json     | 18 ++++++++++
 .../tests/integration/test_controller_cli.json     | 11 +++++++
 .../tests/integration/test_telemetry_contract.json |  6 ++++
 .../tests/unit/test_observer_app.json              | 26 +++++++++++++++
 .../cascade-common/src/cascade/common/inputs.json  | 14 ++++++++
 .../cascade-common/tests/unit/test_messaging.json  | 10 ++++++
 .../cascade-common/tests/unit/test_renderers.json  | 18 ++++++++++
 .../tests/integration/test_local_connector.json    | 18 ++++++++++
 .../tests/unit/conftest.json                       |  6 ++++
 .../tests/unit/test_connector.json                 | 22 +++++++++++++
 .../tests/integration/test_engine_concurrency.json | 18 ++++++++++
 .../tests/integration/test_engine_constraints.json | 38 ++++++++++++++++++++++
 .../integration/test_engine_control_flow.json      | 14 ++++++++
 .../tests/integration/test_engine_core.json        |  6 ++++
 .../test_engine_explicit_control_flow.json         |  6 ++++
 .../integration/test_engine_flow_primitives.json   | 30 +++++++++++++++++
 .../tests/integration/test_engine_inputs.json      | 10 ++++++
 .../tests/integration/test_engine_map.json         | 30 +++++++++++++++++
 .../integration/test_engine_map_policies.json      | 10 ++++++
 .../tests/integration/test_engine_map_reduce.json  | 18 ++++++++++
 .../tests/integration/test_engine_retry.json       | 10 ++++++
 .../integration/test_engine_router_pruning.json    | 10 ++++++
 .../integration/test_file_existence_cache.json     | 10 ++++++
 .../cascade-engine/tests/unit/test_bus.json        | 18 ++++++++++
 .../tests/unit/test_cache_in_memory.json           | 22 +++++++++++++
 .../tests/unit/test_cache_redis.json               | 18 ++++++++++
 .../tests/unit/test_executor_local.json            | 10 ++++++
 .../tests/unit/test_flow_manager.json              | 14 ++++++++
 .../cascade-engine/tests/unit/test_solver_csp.json | 18 ++++++++++
 ...
 83 files changed, 1221 insertions(+), 73 deletions(-)
```