# 📸 Snapshot Capture

### 💬 备注:
ruff and stitcher

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-common/src/cascade/common/context.json  |  9 +++++++++
 .../tests/integration/test_graph_purity.json        | 15 +++++++++++++++
 .../packages/cascade-vm/src/cascade/vm/harness.json |  4 ++--
 .../cascade-vm/src/cascade/vm/protocols.json        | 21 +++++++++++++++++++++
 .../cascade-vm/tests/unit/test_reactor.json         |  4 ++--
 .../tests/integration/test_graph_purity.py          |  5 -----
 .../integration/test_graph_purity.stitcher.yaml     |  4 ++++
 packages/cascade-graph/src/cascade/graph/hashing.py |  4 +++-
 packages/cascade-vm/src/cascade/vm/protocols.py     | 20 +++-----------------
 .../src/cascade/vm/protocols.stitcher.yaml          | 10 ++++++++++
 scripts/lint_hash_names.py                          | 10 +++-------
 11 files changed, 72 insertions(+), 34 deletions(-)
```