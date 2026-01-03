# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/backend/wiring.json       | 28 ++++++++++++
 .../cascade-std/src/cascade/std/probe/const.json   |  4 +-
 .../cascade-std/src/cascade/std/probe/context.json |  4 +-
 .../cascade-std/src/cascade/std/probe/env.json     |  4 +-
 .../cascade-std/src/cascade/std/probe/pulse.json   |  4 +-
 .../src/cascade/std/resource/continuous.json       |  8 ++--
 .../src/cascade/std/resource/discrete.json         |  8 ++--
 .../src/cascade/std/resource/requestor.json        |  4 +-
 .../src/cascade/std/system/drainer.json            |  4 +-
 .../src/cascade/std/system/terminator.json         |  4 +-
 .../src/cascade/std/triad/bleacher.json            |  4 +-
 .../src/cascade/std/triad/observer.json            |  4 +-
 .../cascade-std/src/cascade/std/triad/stainer.json |  4 +-
 .../tests/unit/resource/test_continuous.json       | 18 ++++++--
 .../tests/unit/resource/test_discrete.json         | 22 +++++++---
 .../tests/unit/triad/test_observer.json            | 16 ++++---
 .../cascade-vm/src/cascade/vm/__init__.json        |  3 ++
 .../cascade-vm/src/cascade/vm/harness.json         | 51 ++++++++++++++++++++++
 .../cascade-vm/src/cascade/vm/reactor.json         |  5 ++-
 .../src/cascade/vm/resource_registry.json          | 20 +++++++++
 .../tests/integration/test_branching.json          |  4 +-
 .../integration/test_observability_congestion.json | 14 ++++++
 .../tests/integration/test_ping_pong.json          |  4 +-
 .../integration/test_resource_backpressure.json    |  8 ++--
 .../cascade-vm/tests/unit/test_reactor.json        |  8 +++-
 .../src/cascade/compiler/backend/builder.py        | 28 +++---------
 .../src/cascade/compiler/backend/wiring.py         | 17 ++------
 .../cascade/compiler/backend/wiring.stitcher.yaml  | 11 +++++
 .../src/cascade/std/resource/continuous.py         |  4 +-
 .../src/cascade/std/resource/discrete.py           |  4 +-
 ...
 45 files changed, 296 insertions(+), 151 deletions(-)
```