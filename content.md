# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/backend/expander.py       | 20 +++---
 .../compiler/backend/wiring/policies/control.py    |  2 +-
 .../backend/wiring/policies/observability.py       |  4 +-
 .../compiler/backend/wiring/policies/parameter.py  |  2 +-
 .../compiler/backend/wiring/policies/pulse.py      |  2 +-
 .../compiler/backend/wiring/prisms/discrete.py     |  2 +-
 packages/cascade-compiler/stitcher.lock            |  4 ++
 .../integration/test_resource_backpressure.py      | 20 +++---
 .../tests/unit/backend/test_builder.py             |  2 +-
 .../tests/unit/backend/test_expander.py            |  2 +-
 packages/cascade-reflection/stitcher.lock          | 12 ++++
 packages/cascade-spec/src/cascade/spec/__init__.py |  2 +-
 .../src/cascade/spec/components/__init__.py        |  2 +-
 .../cascade-spec/src/cascade/spec/physical/dyad.py | 10 ---
 .../src/cascade/spec/physical/dyad.stitcher.yaml   |  6 ++
 .../src/cascade/spec/physical/system_nodes.py      |  2 +-
 packages/cascade-spec/stitcher.lock                | 74 ++++++++++++++++++++++
 packages/cascade-std/stitcher.lock                 | 52 +++++++++++++++
 .../cascade-std/tests/unit/dyad/test_lander.py     | 32 ++++------
 .../cascade-std/tests/unit/dyad/test_launcher.py   | 11 ++--
 packages/cascade-vm/src/cascade/vm/linker.py       |  2 +-
 packages/cascade-vm/stitcher.lock                  |  4 ++
 .../tests/integration/test_context_injection.py    | 53 +++++++++-------
 .../tests/integration/test_linker_validation.py    |  2 +-
 .../tests/integration/test_machine_integration.py  | 57 +++++++++--------
 .../tests/unit/physics/test_micro_physics.py       | 23 +++++--
 26 files changed, 280 insertions(+), 124 deletions(-)
```