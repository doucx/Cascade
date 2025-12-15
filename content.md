# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
src/cascade/__init__.py                 | 19 ++++++---
 src/cascade/adapters/executors/local.py | 22 +++++-----
 src/cascade/adapters/solvers/native.py  |  6 ++-
 src/cascade/graph/build.py              | 22 +++++-----
 src/cascade/graph/model.py              | 14 ++++--
 src/cascade/runtime/bus.py              |  6 ++-
 src/cascade/runtime/engine.py           | 76 +++++++++++++++++++++------------
 src/cascade/runtime/events.py           | 30 ++++++++++---
 src/cascade/runtime/protocols.py        | 15 +++----
 src/cascade/runtime/subscribers.py      | 21 ++++++---
 src/cascade/spec/resource.py            | 19 +++++++--
 src/cascade/spec/task.py                | 11 ++++-
 src/cascade/testing.py                  | 11 +++--
 tests/test_adapters.py                  | 43 ++++++++++---------
 tests/test_core_mvp.py                  | 38 +++++++++++------
 tests/test_di_and_resources.py          | 28 +++++++++---
 tests/test_end_to_end.py                | 52 ++++++++++++++--------
 tests/test_runtime_observability.py     | 49 +++++++++++----------
 18 files changed, 312 insertions(+), 170 deletions(-)
```