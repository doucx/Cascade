# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/cascade-engine/pyproject.toml             |  27 -
 .../src/cascade/adapters/__init__.py               |   0
 .../src/cascade/adapters/cache/__init__.py         |   3 -
 .../src/cascade/adapters/cache/in_memory.py        |  27 -
 .../src/cascade/adapters/cache/redis.py            |  40 --
 .../src/cascade/adapters/caching/__init__.py       |   3 -
 .../src/cascade/adapters/caching/file_existence.py |  35 -
 .../src/cascade/adapters/executors/__init__.py     |   0
 .../src/cascade/adapters/executors/local.py        |  28 -
 .../src/cascade/adapters/solvers/__init__.py       |   0
 .../src/cascade/adapters/solvers/csp.py            | 142 ----
 .../src/cascade/adapters/solvers/native.py         |  59 --
 .../src/cascade/adapters/state/__init__.py         |   4 -
 .../src/cascade/adapters/state/in_memory.py        |  33 -
 .../src/cascade/adapters/state/redis.py            |  56 --
 .../src/cascade/connectors/__init__.py             |   3 -
 .../cascade-engine/src/cascade/connectors/local.py | 225 ------
 packages/cascade-engine/src/cascade/graph/build.py | 173 -----
 .../cascade-engine/src/cascade/graph/compiler.py   | 117 ----
 .../cascade-engine/src/cascade/graph/hashing.py    | 108 ---
 .../cascade-engine/src/cascade/graph/serialize.py  | 286 --------
 .../cascade-engine/src/cascade/runtime/__init__.py |  20 -
 packages/cascade-engine/src/cascade/runtime/bus.py |  34 -
 .../src/cascade/runtime/constraints/__init__.py    |   3 -
 .../src/cascade/runtime/constraints/handlers.py    | 198 ------
 .../src/cascade/runtime/constraints/manager.py     | 144 ----
 .../src/cascade/runtime/constraints/protocols.py   |  52 --
 .../cascade/runtime/constraints/rate_limiter.py    |  82 ---
 .../cascade-engine/src/cascade/runtime/engine.py   | 754 ---------------------
 .../cascade-engine/src/cascade/runtime/events.py   | 117 ----
 ...
 144 files changed, 12152 deletions(-)
```