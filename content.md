# 📸 Snapshot Capture

### 💬 备注:
style: ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/backend/builder.json      |  4 +-
 .../tests/integration/test_ref_architecture.json   | 14 +++++
 .../integration/test_resource_backpressure.json    | 14 +++++
 .../integration/test_source_node_execution.json    | 10 ++++
 .../cascade-spec/src/cascade/spec/ir/graph.json    |  1 +
 .../src/cascade/spec/physical/assembly.json        |  5 ++
 .../src/cascade/spec/runtime/system.json           |  4 ++
 .../packages/cascade-vm/src/cascade/vm/linker.json |  8 +++
 .../cascade-vm/src/cascade/vm/reactor.json         |  5 ++
 .../tests/unit/physics/test_micro_physics.json     | 25 ++++++++
 .../cascade-vm/tests/unit/test_linker.json         | 30 ++++++++++
 packages/cascade-vm/src/cascade/vm/linker.py       |  3 -
 .../cascade-vm/src/cascade/vm/linker.stitcher.yaml |  4 ++
 packages/cascade-vm/src/cascade/vm/machine.py      | 10 ++--
 packages/cascade-vm/src/cascade/vm/reactor.py      |  4 +-
 .../tests/integration/test_machine_integration.py  |  2 +-
 .../tests/unit/physics/test_micro_physics.py       | 67 +++++++++-------------
 .../unit/physics/test_micro_physics.stitcher.yaml  | 12 ++++
 packages/cascade-vm/tests/unit/test_linker.py      |  3 +-
 tests/vm/integration/test_machine_integration.py   |  2 +-
 20 files changed, 172 insertions(+), 55 deletions(-)
```