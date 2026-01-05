# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-spec/src/cascade/spec/assembly.json    |   9 --
 .../cascade-spec/src/cascade/spec/binding.json     |   3 -
 .../cascade-spec/src/cascade/spec/constraint.json  |  27 -----
 .../src/cascade/spec/dsl/constraint.json           |  27 +++++
 .../cascade-spec/src/cascade/spec/dsl/fluent.json  |  79 ++++++++++++++
 .../cascade-spec/src/cascade/spec/dsl/inputs.json  |  15 +++
 .../cascade-spec/src/cascade/spec/dsl/jump.json    |  16 +++
 .../src/cascade/spec/dsl/resources.json            |  35 ++++++
 .../cascade-spec/src/cascade/spec/dsl/routing.json |   7 ++
 .../cascade-spec/src/cascade/spec/dsl/task.json    |  35 ++++++
 .../cascade-spec/src/cascade/spec/environment.json |  16 ---
 .../cascade-spec/src/cascade/spec/fingerprint.json |  50 ---------
 .../cascade-spec/src/cascade/spec/input.json       |  15 ---
 .../src/cascade/spec/ir/fingerprint.json           |  50 +++++++++
 .../cascade-spec/src/cascade/spec/ir/graph.json    |  50 +++++++++
 .../cascade-spec/src/cascade/spec/ir/models.json   |  50 ---------
 .../cascade-spec/src/cascade/spec/jump.json        |  16 ---
 .../cascade-spec/src/cascade/spec/lazy_types.json  |  79 --------------
 .../src/cascade/spec/observability.json            |  38 -------
 .../src/cascade/spec/physical/assembly.json        |   9 ++
 .../src/cascade/spec/physical/binding.json         |   3 +
 .../src/cascade/spec/physical/environment.json     |  16 +++
 .../src/cascade/spec/physical/nodes.json           |  42 +++++++
 .../src/cascade/spec/physical/ports.json           |  26 +++++
 .../src/cascade/spec/physical/resources.json       |   5 +
 .../src/cascade/spec/physical/topology.json        |  27 +++++
 .../src/cascade/spec/physical/triad.json           |  14 +++
 .../cascade-spec/src/cascade/spec/physics.json     |  42 -------
 .../cascade-spec/src/cascade/spec/ports.json       |  26 -----
 .../cascade-spec/src/cascade/spec/protocols.json   | 121 ---------------------
 ...
 261 files changed, 1958 insertions(+), 1958 deletions(-)
```