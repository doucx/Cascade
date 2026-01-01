# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-compiler/src/cascade/__init__.json     |  3 +
 .../src/cascade/compiler/backend/__init__.json     |  3 +
 .../src/cascade/compiler/backend/builder.json      | 14 ++++
 .../src/cascade/compiler/backend/expander.json     | 17 +++++
 .../tests/unit/backend/test_builder.json           | 11 +++
 .../tests/unit/backend/test_expander.json          |  6 ++
 .../cascade-spec/src/cascade/spec/ir/models.json   | 19 ++++++
 .../cascade-spec/src/cascade/spec/physics.json     | 38 +++++++++++
 .../cascade-spec/src/cascade/spec/resources.json   |  5 ++
 .../cascade-spec/src/cascade/spec/topology.json    | 26 +++++++
 .../cascade-spec/src/cascade/spec/triad.json       | 14 ++++
 .../packages/cascade-vm/src/cascade/__init__.json  |  3 +
 .../cascade-vm/src/cascade/vm/executor.json        | 15 ++++
 .../src/cascade/vm/instructions/bleacher.json      |  7 ++
 .../src/cascade/vm/instructions/observer.json      | 12 ++++
 .../src/cascade/vm/instructions/stainer.json       |  7 ++
 .../packages/cascade-vm/src/cascade/vm/memory.json | 40 +++++++++++
 .../cascade-vm/src/cascade/vm/reactor.json         | 26 +++++++
 .../tests/integration/test_ping_pong.json          | 17 +++++
 .../tests/unit/instructions/test_bleacher.json     | 22 ++++++
 .../tests/unit/instructions/test_observer.json     | 17 +++++
 .../tests/unit/instructions/test_stainer.json      | 17 +++++
 .../cascade-vm/tests/unit/test_executor.json       | 32 +++++++++
 .../cascade-vm/tests/unit/test_memory.json         | 27 ++++++++
 .../cascade-vm/tests/unit/test_reactor.json        | 31 +++++++++
 .../src/cascade/compiler/backend/__init__.py       |  2 +-
 .../src/cascade/compiler/backend/builder.py        | 20 ++----
 .../cascade/compiler/backend/builder.stitcher.yaml |  4 ++
 .../src/cascade/compiler/backend/expander.py       | 79 ++++++++--------------
 .../compiler/backend/expander.stitcher.yaml        | 10 +++
 ...
 69 files changed, 772 insertions(+), 355 deletions(-)
```