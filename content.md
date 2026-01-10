# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/runtime/host/instance.json         | 17 ++++-
 .../src/cascade/runtime/strategies/__init__.json   |  3 +
 .../src/cascade/runtime/strategies/vm.json         | 60 ++++++++++++++++++
 .../tests/integration/test_vm_e2e.json             | 55 +++++++++++++++++
 .../tests/unit/host/test_engine_init.json          | 24 ++++++++
 .../src/cascade/spec/runtime/strategies.json       |  1 +
 .../src/cascade/vm/compute/adapters.json           | 48 +++++++++++++++
 .../cascade-vm/src/cascade/vm/registry.json        |  3 +-
 .../tests/integration/test_compute_adapters.json   | 72 ++++++++++++++++++++++
 .../cascade-vm/tests/unit/test_registry.json       | 31 ++++++++++
 .../cascade/runtime/host/instance.stitcher.yaml    |  3 -
 .../src/cascade/runtime/strategies/vm.py           | 68 ++++++--------------
 .../cascade/runtime/strategies/vm.stitcher.yaml    | 23 +++++++
 .../tests/integration/test_vm_e2e.py               | 20 +++---
 .../tests/integration/test_vm_e2e.stitcher.yaml    | 10 +++
 .../tests/unit/host/test_engine_init.py            | 11 +---
 .../tests/unit/host/test_engine_init.stitcher.yaml |  6 ++
 .../cascade-vm/src/cascade/vm/compute/adapters.py  | 11 ++--
 .../src/cascade/vm/compute/adapters.stitcher.yaml  |  4 ++
 .../tests/integration/test_compute_adapters.py     | 14 ++---
 .../test_compute_adapters.stitcher.yaml            | 12 ++++
 packages/cascade-vm/tests/unit/test_registry.py    | 16 +++--
 .../tests/unit/test_registry.stitcher.yaml         |  8 +++
 23 files changed, 419 insertions(+), 101 deletions(-)
```