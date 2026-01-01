# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/cascade-compiler/src/cascade/compiler/frontend.py          | 3 +--
 packages/cascade-compiler/src/cascade/compiler/optimizer.py         | 2 +-
 packages/cascade-compiler/tests/unit/test_backend_tco.py            | 3 +--
 packages/cascade-compiler/tests/unit/test_backend_topology.py       | 3 +--
 packages/cascade-compiler/tests/unit/test_frontend.py               | 2 --
 packages/cascade-compiler/tests/unit/test_optimizer.py              | 1 -
 packages/cascade-python/src/cascade/__init__.py                     | 1 -
 packages/cascade-vm/src/cascade/vm/machine.py                       | 6 +-----
 packages/cascade-vm/src/cascade/vm/middleware/standard.py           | 4 ++--
 packages/cascade-vm/src/cascade/vm/reactor/core.py                  | 2 +-
 packages/cascade-vm/tests/reactor/test_polarized_channels.py        | 1 -
 packages/cascade-vm/tests/reactor/test_reactor_loop.py              | 3 +--
 .../cascade-vm/tests/reactor/test_reactor_resource_awareness.py     | 1 -
 packages/cascade-vm/tests/reactor/test_routing_vm.py                | 2 +-
 packages/cascade-vm/tests/unit/test_middleware_pipeline.py          | 5 +----
 packages/cascade-vm/tests/unit/test_vm_map.py                       | 2 +-
 scripts/refactor_identifiers.py                                     | 2 --
 17 files changed, 12 insertions(+), 31 deletions(-)
```