# 📸 Snapshot Capture

### 💬 备注:
ruff

检测到工作区发生变更。

### 📝 变更文件摘要:
```
observatory/agents/kuramoto.py                     |  88 ++++++++--------
 observatory/experiments/run_fireflies.py           | 112 +++++++++++++--------
 observatory/networking/ipc.py                      |   8 +-
 observatory/scripts/debug_headless_throughput.py   |  25 +++--
 observatory/scripts/debug_renderer_throughput.py   |   5 +-
 observatory/scripts/profile_entry.py               |   9 +-
 .../cascade-runtime/src/cascade/graph/compiler.py  |  29 ++++--
 .../src/cascade/runtime/blueprint.py               |  20 +++-
 .../cascade-runtime/src/cascade/runtime/engine.py  |  53 +++++-----
 packages/cascade-runtime/src/cascade/runtime/vm.py |  90 ++++++++++-------
 tests/cascade-runtime/graph/test_compiler.py       |  45 +++++----
 .../integration/test_engine_vm_integration.py      |  50 +++++----
 tests/cascade-runtime/runtime/test_vm.py           |  37 +++----
 .../cascade-runtime/runtime/test_vm_integration.py |  12 ++-
 tests/cascade-runtime/runtime/test_vm_mutual.py    |  20 ++--
 15 files changed, 361 insertions(+), 242 deletions(-)
```