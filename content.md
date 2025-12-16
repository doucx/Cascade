# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
src/cascade/__init__.py                        |   6 +-
 src/cascade/adapters/caching/__init__.py       |   2 +-
 src/cascade/adapters/caching/file_existence.py |   6 +-
 src/cascade/adapters/executors/local.py        |  24 +++--
 src/cascade/graph/build.py                     |  14 +--
 src/cascade/graph/model.py                     |   9 +-
 src/cascade/providers/__init__.py              |  31 +++++--
 src/cascade/providers/http.py                  |  22 +++--
 src/cascade/providers/shell.py                 |   7 +-
 src/cascade/providers/sql.py                   |  34 +++----
 src/cascade/providers/template.py              |   7 +-
 src/cascade/runtime/engine.py                  | 123 ++++++++++++++-----------
 src/cascade/spec/common.py                     |   3 +-
 src/cascade/spec/file.py                       |   8 +-
 src/cascade/spec/routing.py                    |   6 +-
 src/cascade/spec/task.py                       |   7 +-
 src/cascade/tools/events.py                    |  12 ++-
 src/cascade/tools/preview.py                   |  15 +--
 tests/test_caching.py                          |   6 +-
 tests/test_control_flow.py                     |  25 +++--
 tests/test_http.py                             |  25 ++---
 tests/test_map.py                              |  45 +++++----
 tests/test_retry.py                            |  12 +--
 tests/test_routing.py                          |  53 +++++------
 tests/test_spec_async.py                       |  12 ++-
 tests/test_spec_file.py                        |  23 +++--
 tests/test_sql.py                              |  48 +++++-----
 tests/test_stdlib.py                           |  17 ++--
 tests/test_template.py                         |  27 +++---
 tests/test_tools.py                            |  59 +++++++-----
 30 files changed, 383 insertions(+), 305 deletions(-)
```