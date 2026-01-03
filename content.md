# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-spec/src/cascade/spec/ir/models.json     |  2 ++
 .../cascade-spec/src/cascade/spec/ports.json         | 12 ++++++++++++
 .../packages/cascade-vm/src/cascade/vm/memory.json   |  6 ++++++
 .../packages/cascade-vm/src/cascade/vm/reactor.json  | 20 ++++++++++++++++++--
 .../cascade-vm/tests/integration/test_branching.json |  4 ++++
 .../src/cascade/compiler/backend/builder.py          |  4 ++--
 .../src/cascade/compiler/backend/expander.py         | 12 ++++--------
 .../src/cascade/compiler/frontend/generator.py       |  2 +-
 .../src/cascade/compiler/utils/hashing.py            |  4 +++-
 .../integration/test_observability_congestion.py     |  1 +
 packages/cascade-vm/src/cascade/vm/memory.py         |  1 -
 .../cascade-vm/src/cascade/vm/memory.stitcher.yaml   |  2 ++
 packages/cascade-vm/src/cascade/vm/reactor.py        | 18 ++++++------------
 .../cascade-vm/src/cascade/vm/reactor.stitcher.yaml  |  9 +++++----
 .../tests/integration/test_resource_backpressure.py  |  1 +
 15 files changed, 67 insertions(+), 31 deletions(-)
```