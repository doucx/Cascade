# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
conftest.py                                        | 33 ++++------------------
 .../src/cascade/app/__init__.py                    | 10 +++----
 .../src/cascade/providers/subflow.py               |  2 +-
 packages/cascade-library/stitcher.lock             |  8 +++---
 .../tests/integration/test_config.py               |  2 --
 .../cascade-library/tests/integration/test_file.py |  2 --
 .../tests/integration/test_helpers.py              |  4 ---
 .../cascade-library/tests/integration/test_http.py |  2 --
 .../cascade-library/tests/integration/test_io.py   |  2 --
 .../cascade-library/tests/integration/test_s3.py   |  2 --
 .../tests/integration/test_subflow.py              |  2 --
 packages/cascade-provider-ipfs/stitcher.lock       |  8 +++---
 .../src/cascade/runtime/host/__init__.py           |  2 +-
 .../src/cascade/runtime/host/factory.py            | 14 ++++-----
 .../src/cascade/runtime/host/instance.py           |  3 +-
 packages/cascade-runtime/stitcher.lock             |  4 +--
 .../tests/integration/test_engine_concurrency.py   |  1 -
 .../tests/integration/test_engine_constraints.py   |  9 ++++--
 .../tests/integration/test_engine_control_flow.py  |  2 +-
 .../tests/integration/test_engine_core.py          |  2 +-
 .../test_engine_explicit_control_flow.py           |  3 +-
 .../integration/test_engine_flow_primitives.py     |  2 +-
 .../tests/integration/test_engine_inputs.py        |  2 +-
 .../tests/integration/test_engine_map.py           |  2 +-
 .../tests/integration/test_engine_map_policies.py  |  2 +-
 .../tests/integration/test_engine_map_reduce.py    |  2 +-
 .../tests/integration/test_engine_retry.py         |  1 -
 .../integration/test_engine_router_pruning.py      |  2 +-
 .../tests/integration/test_vm_e2e.py               |  1 -
 .../integration/test_static_integrity.py           |  2 +-
 ...
 42 files changed, 69 insertions(+), 124 deletions(-)
```