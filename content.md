# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/connectors/mqtt/__init__.py        |   2 +-
 .../src/cascade/connectors/mqtt/connector.py       |  16 +-
 .../cascade-connector-mqtt/tests/test_connector.py | 163 -------------------
 .../src/cascade/spec/constraint.py                 |   2 +-
 .../src/cascade/runtime/constraints.py             |   4 +-
 .../cascade-runtime/src/cascade/runtime/engine.py  |   4 +-
 tests/connector-mqtt/test_connector.py             | 178 +++++++++++++++++++++
 tests/py/runtime/test_engine_constraints.py        |  22 ++-
 8 files changed, 207 insertions(+), 184 deletions(-)
```