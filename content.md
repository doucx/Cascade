# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/cascade-interfaces/pyproject.toml         |  12 --
 .../cascade-interfaces/src/cascade/graph/model.py  |  76 -----------
 .../src/cascade/interfaces/protocols.py            | 144 ---------------------
 .../src/cascade/spec/__init__.py                   |   0
 .../cascade-interfaces/src/cascade/spec/common.py  |  12 --
 .../src/cascade/spec/constraint.py                 |  38 ------
 .../cascade-interfaces/src/cascade/spec/input.py   |  27 ----
 .../src/cascade/spec/lazy_types.py                 |  58 ---------
 .../src/cascade/spec/resource.py                   |  53 --------
 .../cascade-interfaces/src/cascade/spec/routing.py |  18 ---
 .../cascade-interfaces/src/cascade/spec/task.py    | 114 ----------------
 .../src/cascade/spec/telemetry.py                  |  42 ------
 .../cascade-spec/cascade-interfaces/pyproject.toml |  12 ++
 .../cascade-interfaces/src/cascade/graph/model.py  |  76 +++++++++++
 .../src/cascade/interfaces/protocols.py            | 144 +++++++++++++++++++++
 .../src/cascade/spec/__init__.py                   |   0
 .../cascade-interfaces/src/cascade/spec/common.py  |  12 ++
 .../src/cascade/spec/constraint.py                 |  38 ++++++
 .../cascade-interfaces/src/cascade/spec/input.py   |  27 ++++
 .../src/cascade/spec/lazy_types.py                 |  58 +++++++++
 .../src/cascade/spec/resource.py                   |  53 ++++++++
 .../cascade-interfaces/src/cascade/spec/routing.py |  18 +++
 .../cascade-interfaces/src/cascade/spec/task.py    | 114 ++++++++++++++++
 .../src/cascade/spec/telemetry.py                  |  42 ++++++
 24 files changed, 594 insertions(+), 594 deletions(-)
```