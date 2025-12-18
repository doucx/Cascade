# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-interfaces/src/cascade/graph/model.py  | 15 ++--
 .../src/cascade/interfaces/protocols.py            |  4 +-
 .../cascade-interfaces/src/cascade/spec/input.py   |  8 +-
 .../cascade-interfaces/src/cascade/spec/task.py    |  1 +
 .../src/cascade/spec/telemetry.py                  | 18 ++--
 packages/cascade-py/src/cascade/__init__.py        | 21 +++--
 packages/cascade-py/src/cascade/context.py         |  5 +-
 .../src/cascade/examples/patterns/llm_openai.py    | 13 ++-
 packages/cascade-py/src/cascade/internal/inputs.py |  6 +-
 packages/cascade-py/src/cascade/messaging/bus.py   |  7 +-
 .../cascade-py/src/cascade/messaging/renderer.py   |  7 +-
 .../cascade-py/src/cascade/providers/__init__.py   |  1 +
 packages/cascade-py/src/cascade/providers/http.py  | 34 ++++++--
 packages/cascade-py/src/cascade/providers/io.py    | 29 ++++++-
 packages/cascade-py/src/cascade/providers/s3.py    | 21 +++--
 packages/cascade-py/src/cascade/providers/shell.py |  2 +-
 packages/cascade-py/src/cascade/providers/stdio.py |  8 +-
 .../cascade-py/src/cascade/providers/subflow.py    |  6 +-
 .../cascade-py/src/cascade/providers/template.py   |  1 +
 packages/cascade-py/src/cascade/tools/cli.py       | 14 ++--
 packages/cascade-py/src/cascade/tools/visualize.py |  8 +-
 .../src/cascade/adapters/cache/__init__.py         |  2 +-
 .../src/cascade/adapters/cache/in_memory.py        |  2 +-
 .../src/cascade/adapters/solvers/csp.py            | 58 ++++++-------
 .../src/cascade/adapters/solvers/native.py         | 18 ++--
 .../src/cascade/adapters/state/__init__.py         |  2 +-
 .../src/cascade/adapters/state/in_memory.py        |  2 +-
 .../cascade-runtime/src/cascade/graph/build.py     | 36 ++++----
 .../cascade-runtime/src/cascade/graph/serialize.py | 31 +++----
 .../cascade-runtime/src/cascade/runtime/engine.py  | 97 +++++++++++++++-------
 ...
 63 files changed, 825 insertions(+), 522 deletions(-)
```