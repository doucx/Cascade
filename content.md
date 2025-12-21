# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
observatory/scripts/analyze_logs.py                | 104 ++++++++++++---------
 .../cascade-cli-controller/src/cascade/__init__.py |   2 +-
 .../cascade-cli-observer/src/cascade/__init__.py   |   2 +-
 .../cascade-connector-mqtt/src/cascade/__init__.py |   2 +-
 .../src/cascade/connectors/__init__.py             |   2 +-
 .../cascade-provider-ipfs/src/cascade/__init__.py  |   2 +-
 .../src/cascade/providers/__init__.py              |   2 +-
 .../src/cascade/providers/ipfs/__init__.py         |   2 +-
 .../cascade-py/src/cascade/providers/__init__.py   |   2 +-
 .../cascade-py/src/cascade/providers/helpers.py    |   8 +-
 .../cascade-py/src/cascade/providers/registry.py   |   2 +-
 packages/cascade-py/src/cascade/tools/preview.py   |   7 +-
 .../cascade-runtime/src/cascade/graph/build.py     |  22 +++--
 .../src/cascade/runtime/resolvers.py               |  62 +++++++-----
 tests/cascade-py/providers/test_helpers.py         |  28 ++----
 tests/cascade-runtime/graph/test_build.py          |  12 ++-
 16 files changed, 148 insertions(+), 113 deletions(-)
```