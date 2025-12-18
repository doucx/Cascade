# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/cli/__init__.py                    |  2 +-
 .../src/cascade/cli/controller/app.py              | 14 +++++---
 .../src/cascade/cli/__init__.py                    |  2 +-
 .../src/cascade/cli/observer/app.py                | 11 ++++---
 .../src/cascade/cli/observer/rendering.py          | 23 ++++++-------
 packages/cascade-common/src/cascade/__init__.py    |  2 +-
 .../cascade-common/src/cascade/common/__init__.py  |  2 +-
 .../cascade/common/locales/en/cli_messages.json    |  3 +-
 .../src/cascade/common/messaging/__init__.py       |  2 +-
 .../src/cascade/common/messaging/bus.py            |  2 +-
 .../src/cascade/common/messaging/protocols.py      |  2 +-
 .../cascade-common/src/cascade/common/renderers.py |  2 +-
 .../src/cascade/connectors/mqtt/connector.py       |  2 +-
 .../src/cascade/runtime/constraints/__init__.py    |  2 +-
 .../src/cascade/runtime/constraints/handlers.py    |  4 +--
 .../src/cascade/runtime/constraints/manager.py     |  2 +-
 .../src/cascade/runtime/constraints/protocols.py   |  2 +-
 .../cascade-runtime/src/cascade/runtime/engine.py  |  7 ++--
 .../src/cascade/runtime/resolvers.py               | 12 +++++--
 .../src/cascade/runtime/subscribers.py             |  4 +--
 tests/cli-controller/test_controller_app.py        |  8 ++---
 tests/cli-observer/test_observer_app.py            |  9 ++---
 tests/common/test_messaging.py                     | 14 ++++----
 tests/common/test_renderers.py                     |  2 +-
 tests/py/e2e/test_e2e_concurrency_control.py       | 15 ++++++---
 tests/py/runtime/test_engine_concurrency.py        | 38 +++++++++++++---------
 tests/runtime/test_event_bus.py                    |  2 +-
 27 files changed, 111 insertions(+), 79 deletions(-)
```