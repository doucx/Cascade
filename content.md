# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/cascade-compiler/pyproject.toml           |  20 ---
 .../src/cascade/compiler/__init__.py               |  15 --
 .../src/cascade/compiler/backend.py                |  94 ----------
 .../src/cascade/compiler/exceptions.py             |   7 -
 .../src/cascade/compiler/frontend.py               | 126 -------------
 .../src/cascade/compiler/optimizer.py              |  81 ---------
 .../cascade-compiler/tests/unit/test_backend.py    |  97 ----------
 .../cascade-compiler/tests/unit/test_frontend.py   |  70 --------
 .../cascade-compiler/tests/unit/test_optimizer.py  |  72 --------
 packages/cascade-engine/pyproject.toml             |   3 +-
 .../src/cascade/runtime/strategies/vm.py           |  47 ++---
 .../cascade/runtime/strategies/vm.stitcher.yaml    |   4 +-
 .../tests/integration/test_compiler.py             |  60 -------
 .../cascade-spec/src/cascade/spec/ir/__init__.py   |  24 +--
 .../cascade-spec/src/cascade/spec/ir/models.py     |  45 +----
 packages/cascade-spec/tests/unit/test_ir_models.py |  95 ----------
 packages/cascade-vm/pyproject.toml                 |  23 ---
 packages/cascade-vm/src/cascade/vm/__init__.py     |   6 -
 packages/cascade-vm/src/cascade/vm/machine.py      | 195 ---------------------
 packages/cascade-vm/src/cascade/vm/protocols.py    |   9 -
 packages/cascade-vm/tests/unit/test_vm_basic.py    |  86 ---------
 pyproject.toml                                     |   6 -
 .../e2e/integration/test_engine_vm_integration.py  |  30 +---
 23 files changed, 27 insertions(+), 1188 deletions(-)
```