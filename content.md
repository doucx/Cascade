# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
conftest.py                                                           | 2 +-
 packages/cascade-compiler/src/cascade/compiler/__init__.py            | 4 ----
 packages/cascade-compiler/src/cascade/compiler/backend/builder.py     | 4 ++--
 .../src/cascade/compiler/backend/expansion/policies/control.py        | 2 +-
 .../src/cascade/compiler/backend/expansion/policies/parameter.py      | 2 +-
 .../src/cascade/compiler/backend/expansion/policies/pulse.py          | 2 +-
 .../src/cascade/compiler/backend/expansion/policies/resource.py       | 2 +-
 .../src/cascade/compiler/backend/wiring/policies/control.py           | 2 +-
 .../src/cascade/compiler/backend/wiring/policies/observability.py     | 2 +-
 .../src/cascade/compiler/backend/wiring/policies/parameter.py         | 2 +-
 .../src/cascade/compiler/backend/wiring/policies/pulse.py             | 2 +-
 .../src/cascade/compiler/backend/wiring/policies/resource.py          | 2 +-
 .../cascade-compiler/src/cascade/compiler/backend/wiring/protocol.py  | 0
 packages/cascade-test-utils/src/cascade/test_utils/harness.py         | 2 +-
 packages/cascade-vm/src/cascade/vm/__init__.py                        | 3 +--
 packages/cascade-vm/src/cascade/vm/machine.py                         | 2 +-
 packages/cascade-vm/src/cascade/vm/protocols.py                       | 0
 17 files changed, 15 insertions(+), 20 deletions(-)
```