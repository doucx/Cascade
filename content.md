# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-application/src/cascade/__init__.json  |   3 -
 .../src/cascade/app/__init__.json                  |  70 -------------
 .../tests/integration/test_app_tools.json          |  17 ----
 .../cascade-application/tests/test_app_tools.json  |  17 ----
 .../src/cascade/__init__.json                      |   3 -
 .../src/cascade/cli/__init__.json                  |   3 -
 .../src/cascade/cli/controller/app.json            |  41 --------
 .../tests/integration/test_controller_app.json     |  22 -----
 .../tests/integration/test_controller_cli.json     |  12 ---
 .../tests/test_controller_app.json                 |  22 -----
 .../tests/test_controller_cli.json                 |  12 ---
 .../cascade-cli-observer/src/cascade/__init__.json |   3 -
 .../src/cascade/cli/__init__.json                  |   3 -
 .../src/cascade/cli/observer/app.json              |  49 ----------
 .../src/cascade/cli/observer/rendering.json        |  18 ----
 .../tests/integration/test_telemetry_contract.json |   7 --
 .../tests/test_observer_app.json                   |  32 ------
 .../tests/test_telemetry_contract.json             |   7 --
 .../tests/unit/test_observer_app.json              |  32 ------
 .../cascade-common/src/cascade/__init__.json       |   3 -
 .../cascade-common/src/cascade/common/context.json |  30 ------
 .../cascade-common/src/cascade/common/inputs.json  |  15 ---
 .../src/cascade/common/messaging/__init__.json     |   3 -
 .../src/cascade/common/messaging/bus.json          | 108 ---------------------
 .../src/cascade/common/messaging/protocols.json    |  10 --
 .../src/cascade/common/renderers.json              |  30 ------
 .../cascade-common/tests/test_messaging.json       |  12 ---
 .../cascade-common/tests/test_renderers.json       |  18 ----
 .../cascade-common/tests/unit/test_messaging.json  |  12 ---
 .../cascade-common/tests/unit/test_renderers.json  |  18 ----
 ...
 527 files changed, 7014 insertions(+), 11522 deletions(-)
```