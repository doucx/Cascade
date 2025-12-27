# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-application/src/cascade/app/__init__.py   | 19 -------------------
 .../src/cascade/app/__init__.stitcher.yaml            | 17 +++++++++++++++++
 packages/cascade-application/tests/test_app_tools.py  | 11 -----------
 .../tests/test_app_tools.stitcher.yaml                |  8 ++++++++
 .../src/cascade/cli/controller/app.py                 | 17 -----------------
 .../src/cascade/cli/controller/app.stitcher.yaml      | 17 +++++++++++++++++
 .../tests/test_controller_app.py                      |  8 --------
 .../tests/test_controller_app.stitcher.yaml           |  8 ++++++++
 .../tests/test_controller_cli.py                      |  4 ----
 .../tests/test_controller_cli.stitcher.yaml           |  3 +++
 .../src/cascade/cli/observer/app.py                   | 12 ------------
 .../src/cascade/cli/observer/app.stitcher.yaml        | 16 ++++++++++++++++
 .../src/cascade/cli/observer/rendering.py             |  3 ---
 .../src/cascade/cli/observer/rendering.stitcher.yaml  |  2 ++
 .../cascade-cli-observer/tests/test_observer_app.py   | 14 --------------
 .../tests/test_observer_app.stitcher.yaml             | 12 ++++++++++++
 .../tests/test_telemetry_contract.py                  |  4 ----
 .../tests/test_telemetry_contract.stitcher.yaml       |  3 +++
 .../src/cascade/common/messaging/protocols.py         | 13 -------------
 .../cascade/common/messaging/protocols.stitcher.yaml  | 11 +++++++++++
 .../cascade-common/src/cascade/common/renderers.py    |  7 -------
 .../src/cascade/common/renderers.stitcher.yaml        |  4 ++++
 packages/cascade-common/tests/test_messaging.py       |  2 --
 .../cascade-common/tests/test_messaging.stitcher.yaml |  4 ++++
 .../src/cascade/connectors/local/bus.py               | 17 -----------------
 .../src/cascade/connectors/local/bus.stitcher.yaml    | 17 +++++++++++++++++
 .../src/cascade/connectors/local/connector.py         |  1 -
 .../cascade/connectors/local/connector.stitcher.yaml  |  2 ++
 .../src/cascade/connectors/local/uds_server.py        |  7 -------
 .../cascade/connectors/local/uds_server.stitcher.yaml | 10 ++++++++++
 ...
 274 files changed, 1276 insertions(+), 1288 deletions(-)
```