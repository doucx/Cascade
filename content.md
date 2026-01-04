# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/backend/builder.json      |  4 +-
 .../src/cascade/compiler/backend/expander.json     |  3 +-
 .../tests/integration/test_assembly_purity.json    | 15 ++++++
 .../src/cascade/runtime/event_bus.json             |  5 ++
 .../cascade-engine/src/cascade/runtime/events.json | 12 ++++-
 .../src/cascade/runtime/strategies/vm.json         | 15 ++++--
 .../tests/integration/test_vm_strategy.json        | 15 ++++++
 .../tests/unit/test_event_translation.json         | 22 +++++++++
 .../cascade-spec/src/cascade/spec/assembly.json    |  9 ++++
 .../src/cascade/spec/observability.json            | 38 +++++++++++++++
 .../tests/unit/test_observability.json             | 14 ++++++
 .../src/cascade/std/triad/observer.json            |  4 +-
 .../tests/unit/triad/test_observer.json            | 16 ++++++-
 .../cascade-vm/src/cascade/vm/harness.json         | 13 +++--
 .../packages/cascade-vm/src/cascade/vm/linker.json | 19 ++++++++
 .../cascade-vm/src/cascade/vm/registry.json        | 25 ++++++++++
 .../tests/integration/test_assembly_purity.py      |  7 +--
 .../integration/test_assembly_purity.stitcher.yaml |  4 ++
 .../tests/integration/test_resource_contention.py  | 20 +++++---
 .../src/cascade/runtime/event_bus.py               |  5 --
 .../src/cascade/runtime/event_bus.stitcher.yaml    |  4 ++
 .../cascade-engine/src/cascade/runtime/events.py   | 12 ++---
 .../src/cascade/runtime/events.stitcher.yaml       |  3 ++
 .../src/cascade/runtime/strategies/vm.py           | 54 ++++++++++-----------
 .../cascade/runtime/strategies/vm.stitcher.yaml    |  2 +
 .../tests/integration/test_vm_strategy.py          |  7 +--
 .../integration/test_vm_strategy.stitcher.yaml     |  2 +
 .../tests/unit/test_event_translation.py           | 55 ++++++++++++----------
 packages/cascade-spec/src/cascade/spec/assembly.py |  8 +---
 .../src/cascade/spec/assembly.stitcher.yaml        |  4 ++
 ...
 46 files changed, 399 insertions(+), 222 deletions(-)
```