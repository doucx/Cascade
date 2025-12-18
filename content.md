# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/cli/controller/app.py              |  8 ++----
 .../src/cascade/cli/observer/app.py                |  2 --
 .../src/cascade/cli/observer/rendering.py          |  1 -
 .../src/cascade/connectors/mqtt/connector.py       | 16 +++++------
 .../src/cascade/runtime/constraints/handlers.py    | 23 +++++++++-------
 .../src/cascade/runtime/constraints/manager.py     |  1 +
 .../cascade/runtime/constraints/rate_limiter.py    | 15 +++++------
 tests/cli-controller/test_controller_cli.py        | 14 ++++++----
 tests/cli-observer/test_telemetry_contract.py      | 21 ++++++++++-----
 tests/py/e2e/harness.py                            | 12 ++++++---
 tests/py/e2e/test_e2e_control_plane.py             |  7 +++--
 tests/py/e2e/test_e2e_rate_limit_control.py        |  6 ++---
 tests/py/e2e/test_e2e_ttl.py                       | 31 ++++++++++++++--------
 tests/py/runtime/test_engine_constraints.py        |  2 +-
 14 files changed, 91 insertions(+), 68 deletions(-)
```