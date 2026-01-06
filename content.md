# 📸 Snapshot Capture

### 💬 备注:
ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/runtime/storage/__init__.json      |  3 ++
 .../src/cascade/runtime/storage/memory.json        | 30 +++++++++++++++++
 .../src/cascade/spec/physical/object.json          | 11 +++++++
 .../src/cascade/spec/physical/triad.json           |  3 +-
 .../src/cascade/spec/runtime/__init__.json         |  3 ++
 .../src/cascade/spec/runtime/compute.json          | 10 ++++++
 .../src/cascade/spec/runtime/storage.json          | 25 ++++++++++++++
 .../src/cascade/std/triad/__init__.json            |  3 ++
 .../src/cascade/std/triad/dispatcher.json          |  8 +++++
 .../src/cascade/vm/compute/__init__.json           |  3 ++
 .../src/cascade/vm/compute/contract.json           | 17 ++++++++++
 .../cascade-vm/src/cascade/vm/compute/service.json | 33 +++++++++++++++++++
 .../cascade-vm/src/cascade/vm/harness.json         | 14 ++++++--
 .../cascade-vm/src/cascade/vm/kernel/__init__.json |  3 ++
 .../cascade-vm/src/cascade/vm/kernel/core.json     | 18 ++++++++++
 .../cascade-vm/tests/unit/test_physics_kernel.json | 38 ++++++++++++++++++++++
 .../src/cascade/runtime/storage/__init__.py        |  2 +-
 .../src/cascade/runtime/storage/memory.py          | 34 ++++---------------
 .../cascade/runtime/storage/memory.stitcher.yaml   | 13 ++++++++
 .../src/cascade/spec/physical/object.py            | 13 --------
 .../src/cascade/spec/physical/object.stitcher.yaml | 11 +++++++
 .../src/cascade/spec/runtime/__init__.py           |  2 +-
 .../src/cascade/spec/runtime/compute.py            | 21 +-----------
 .../src/cascade/spec/runtime/compute.stitcher.yaml | 15 +++++++++
 .../src/cascade/spec/runtime/storage.py            | 31 +++---------------
 .../src/cascade/spec/runtime/storage.stitcher.yaml | 13 ++++++++
 .../src/cascade/std/triad/dispatcher.py            | 12 +++----
 .../src/cascade/std/triad/dispatcher.stitcher.yaml |  5 +++
 .../cascade-vm/src/cascade/vm/compute/__init__.py  |  2 +-
 .../cascade-vm/src/cascade/vm/compute/contract.py  | 12 -------
 ...
 42 files changed, 360 insertions(+), 173 deletions(-)
```