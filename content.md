# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-spec/src/cascade/spec/ir/models.json   |  3 +
 .../cascade-spec/src/cascade/spec/physics.json     |  3 +
 .../cascade-spec/src/cascade/spec/topology.json    |  3 +
 .../src/cascade/vm/instructions/bleacher.json      |  6 +-
 .../cascade-vm/src/cascade/vm/reactor.json         | 10 ++-
 .../tests/integration/test_branching.json          | 19 +++++
 .../tests/integration/test_ping_pong.json          |  4 +-
 .../integration/test_resource_backpressure.json    | 10 +++
 .../cascade-vm/tests/unit/test_reactor.json        |  4 +-
 .../src/cascade/compiler/backend/builder.py        | 28 +++----
 .../src/cascade/spec/ir/models.stitcher.yaml       |  2 +
 .../src/cascade/spec/physics.stitcher.yaml         |  2 +
 .../src/cascade/spec/topology.stitcher.yaml        |  3 +
 .../src/cascade/vm/instructions/bleacher.py        | 10 +--
 .../cascade/vm/instructions/bleacher.stitcher.yaml | 15 +---
 .../src/cascade/vm/instructions/stainer.py         |  2 +-
 packages/cascade-vm/src/cascade/vm/reactor.py      |  9 +--
 .../src/cascade/vm/reactor.stitcher.yaml           |  3 +
 .../cascade-vm/tests/integration/test_branching.py | 29 +++----
 .../tests/integration/test_branching.stitcher.yaml |  4 +
 .../cascade-vm/tests/integration/test_ping_pong.py | 18 ++---
 .../integration/test_resource_backpressure.py      | 93 +++++++++++-----------
 packages/cascade-vm/tests/unit/test_reactor.py     |  4 +-
 23 files changed, 159 insertions(+), 125 deletions(-)
```