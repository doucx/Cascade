# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
observatory/protoplasm/physics/recursion_test.py                  | 2 +-
 packages/cascade-application/src/cascade/app/__init__.py          | 4 ++--
 packages/cascade-cli-controller/src/cascade/cli/controller/app.py | 2 +-
 packages/cascade-cli-observer/src/cascade/cli/observer/app.py     | 2 +-
 .../cascade-cli-observer/src/cascade/cli/observer/rendering.py    | 5 +++--
 .../tests/integration/test_telemetry_contract.py                  | 2 +-
 packages/cascade-common/src/cascade/common/renderers.py           | 7 ++++---
 packages/cascade-common/tests/unit/test_messaging.py              | 3 ++-
 packages/cascade-common/tests/unit/test_renderers.py              | 2 +-
 .../cascade-connector-local/src/cascade/connectors/local/bus.py   | 2 +-
 .../src/cascade/execution/graph/logic/processor.py                | 4 ++--
 .../src/cascade/execution/graph/strategy.py                       | 4 ++--
 packages/cascade-runtime/src/cascade/runtime/__init__.py          | 4 ++--
 packages/cascade-runtime/src/cascade/runtime/host/instance.py     | 4 ++--
 .../src/cascade/runtime/services/constraints/handlers.py          | 2 +-
 .../src/cascade/runtime/services/observability/subscribers.py     | 6 +++---
 .../src/cascade/runtime/services/resources/container.py           | 4 ++--
 packages/cascade-runtime/src/cascade/runtime/strategies/vm.py     | 2 +-
 .../cascade-runtime/tests/integration/test_engine_constraints.py  | 8 ++++----
 .../cascade-runtime/tests/integration/test_engine_control_flow.py | 2 +-
 .../tests/integration/test_engine_flow_primitives.py              | 2 +-
 .../cascade-runtime/tests/integration/test_engine_map_policies.py | 2 +-
 packages/cascade-runtime/tests/integration/test_engine_retry.py   | 2 +-
 .../tests/integration/test_engine_router_pruning.py               | 2 +-
 packages/cascade-runtime/tests/integration/test_vm_e2e.py         | 2 +-
 packages/cascade-runtime/tests/unit/test_bus.py                   | 4 ++--
 packages/cascade-runtime/tests/unit/test_event_translation.py     | 2 +-
 packages/cascade-sdk/src/cascade/sdk.py                           | 4 ++--
 packages/cascade-sdk/src/cascade/tools/events.py                  | 2 +-
 packages/cascade-spec/tests/integration/test_resource.py          | 2 +-
 ...
 47 files changed, 67 insertions(+), 64 deletions(-)
```