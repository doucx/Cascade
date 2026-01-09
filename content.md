# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/execution/graph/errors.json        | 22 +++++++++
 .../src/cascade/execution/graph/logic/flow.json    | 40 +++++++++++++++
 .../cascade/execution/graph/logic/processor.json   | 44 +++++++++++++++++
 .../cascade/execution/graph/logic/resolvers.json   | 42 ++++++++++++++++
 .../cascade/execution/graph/model/__init__.json    |  3 ++
 .../src/cascade/execution/graph/model/adapter.json | 45 +++++++++++++++++
 .../src/cascade/execution/graph/model/build.json   |  7 +++
 .../cascade/execution/graph/model/exceptions.json  |  4 ++
 .../src/cascade/execution/graph/model/hashing.json | 15 ++++++
 .../src/cascade/execution/graph/model/model.json   | 57 ++++++++++++++++++++++
 .../cascade/execution/graph/model/registry.json    | 16 ++++++
 .../cascade/execution/graph/model/serialize.json   | 40 +++++++++++++++
 .../src/cascade/execution/graph/solvers/csp.json   | 19 ++++++++
 .../cascade/execution/graph/solvers/native.json    | 10 ++++
 .../src/cascade/execution/graph/strategy.json      | 45 +++++++++++++++++
 .../src/cascade/runtime/errors.json                | 22 ---------
 .../src/cascade/runtime/graph/__init__.json        |  3 --
 .../src/cascade/runtime/graph/adapter.json         | 45 -----------------
 .../src/cascade/runtime/graph/build.json           |  7 ---
 .../src/cascade/runtime/graph/exceptions.json      |  4 --
 .../src/cascade/runtime/graph/hashing.json         | 15 ------
 .../src/cascade/runtime/graph/model.json           | 57 ----------------------
 .../src/cascade/runtime/graph/registry.json        | 16 ------
 .../src/cascade/runtime/graph/serialize.json       | 40 ---------------
 .../src/cascade/runtime/kernel/solvers/csp.json    | 19 --------
 .../src/cascade/runtime/kernel/solvers/native.json | 10 ----
 .../src/cascade/runtime/legacy/flow.json           | 40 ---------------
 .../src/cascade/runtime/legacy/processor.json      | 44 -----------------
 .../src/cascade/runtime/legacy/resolvers.json      | 42 ----------------
 .../cascade/runtime/legacy/strategies/graph.json   | 45 -----------------
 ...
 154 files changed, 2855 insertions(+), 2877 deletions(-)
```