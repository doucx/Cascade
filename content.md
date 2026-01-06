# 📸 Snapshot Capture

### 💬 备注:
ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-vm/src/cascade/vm/compute/service.json |   5 +
 .../cascade-vm/src/cascade/vm/machine.json         |  18 +++
 .../cascade-vm/src/cascade/vm/reactor.json         |  12 +-
 .../tests/integration/test_context_injection.json  |   9 ++
 .../tests/integration/test_branching.py            |   1 -
 .../src/cascade/runtime/legacy/strategies/vm.py    | 160 +--------------------
 packages/cascade-vm/src/cascade/vm/machine.py      |  20 +--
 .../src/cascade/vm/machine.stitcher.yaml           |   4 +
 packages/cascade-vm/src/cascade/vm/reactor.py      |  18 ++-
 .../tests/integration/test_broker_starvation.py    |   1 -
 .../tests/integration/test_context_injection.py    |  22 +--
 .../test_context_injection.stitcher.yaml           |   3 +
 .../cascade-vm/tests/integration/test_ping_pong.py |   1 -
 .../integration/test_resource_backpressure.py      |   4 +-
 14 files changed, 75 insertions(+), 203 deletions(-)
```