# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
observatory/agents/kuramoto.py                     |   2 +-
 observatory/benchmarks/tco_performance.py          |   2 +-
 packages/cascade-cli-controller/pyproject.toml     |   4 +-
 .../cascade-cli-controller/src/cascade/__init__.py |   2 +-
 .../src/cascade/cli/__init__.py                    |   2 +-
 packages/cascade-cli-observer/pyproject.toml       |   4 +-
 .../cascade-cli-observer/src/cascade/__init__.py   |   2 +-
 .../src/cascade/cli/__init__.py                    |   2 +-
 packages/cascade-common/src/cascade/__init__.py    |   2 +-
 packages/cascade-connector-mqtt/pyproject.toml     |   4 +-
 .../cascade-connector-mqtt/src/cascade/__init__.py |   2 +-
 .../src/cascade/connectors/mqtt/__init__.py        |   2 +-
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
 packages/cascade-provider-ipfs/pyproject.toml      |   4 +-
 .../cascade-provider-ipfs/src/cascade/__init__.py  |   2 +-
 .../src/cascade/providers/__init__.py              |   2 +-
 packages/cascade-py/pyproject.toml                 |   4 +-
 packages/cascade-py/src/cascade/__init__.py        |   2 +-
 packages/cascade-py/src/cascade/tools/visualize.py |   2 +-
 ...
 56 files changed, 126 insertions(+), 720 deletions(-)
```