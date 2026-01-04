# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../tests/integration/test_vm_telemetry.json       |  7 +++
 .../cascade-vm/src/cascade/vm/harness.json         |  5 +-
 .../cascade-vm/src/cascade/vm/protocols.json       |  4 +-
 .../cascade-vm/src/cascade/vm/reactor.json         |  4 +-
 .../tests/integration/test_context_injection.json  | 15 ++++++
 .../src/cascade/runtime/strategies/vm.py           |  6 ++-
 .../tests/integration/test_vm_telemetry.py         | 26 +++-------
 .../integration/test_vm_telemetry.stitcher.yaml    |  4 ++
 packages/cascade-vm/src/cascade/vm/protocols.py    |  3 +-
 packages/cascade-vm/src/cascade/vm/reactor.py      |  4 +-
 .../tests/integration/test_context_injection.py    | 60 +++++++++++++---------
 .../test_context_injection.stitcher.yaml           |  3 ++
 12 files changed, 86 insertions(+), 55 deletions(-)
```