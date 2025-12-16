# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
src/cascade/__init__.py                       |   8 +-
 src/cascade/adapters/executors/local.py       |   4 +-
 src/cascade/graph/build.py                    |   9 +-
 src/cascade/graph/serialize.py                |  74 ++++++-------
 src/cascade/providers/__init__.py             |   2 +-
 src/cascade/providers/config.py               |  13 ++-
 src/cascade/providers/file.py                 |  14 ++-
 src/cascade/runtime/__init__.py               |   2 +-
 src/cascade/runtime/engine.py                 | 143 +++++++++++++++-----------
 src/cascade/runtime/exceptions.py             |   4 +-
 src/cascade/runtime/resolvers.py              |  39 +++----
 src/cascade/runtime/resource_manager.py       |  17 +--
 src/cascade/spec/constraint.py                |   9 +-
 src/cascade/spec/lazy_types.py                |  13 +--
 src/cascade/spec/routing.py                   |   2 +-
 src/cascade/spec/task.py                      |  36 +++++--
 src/cascade/tools/cli.py                      |   2 +-
 src/cascade/tools/preview.py                  |   2 +-
 src/cascade/tools/visualize.py                |   2 +-
 tests/adapters/executors/test_local.py        |  25 ++---
 tests/graph/test_serialize.py                 |  22 ++--
 tests/integration/test_end_to_end.py          |   2 +-
 tests/integration/test_resource_scheduling.py |  31 +++---
 tests/providers/test_config.py                |  38 ++++---
 tests/providers/test_file.py                  |  46 ++++-----
 tests/runtime/test_bus.py                     |   2 +-
 tests/runtime/test_control_flow.py            |   4 +-
 tests/runtime/test_retry.py                   |   5 +-
 tests/spec/test_constraint.py                 |  16 +--
 tests/tools/test_cli.py                       |  10 +-
 ...
 31 files changed, 341 insertions(+), 257 deletions(-)
```