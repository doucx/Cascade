# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/compiler/backend/builder.json      |  1 +
 .../src/cascade/compiler/backend/validator.json    | 24 +++++++
 .../src/cascade/compiler/utils/naming.json         | 20 ++++++
 .../cascade-spec/src/cascade/spec/ports.json       |  2 +
 .../cascade-std/src/cascade/std/probe/const.json   |  7 ++
 .../src/cascade/std/resource/__init__.json         |  3 +
 .../src/cascade/std/resource/continuous.json       |  8 +++
 .../src/cascade/std/resource/discrete.json         | 10 +++
 .../src/cascade/std/resource/requestor.json        |  7 ++
 .../tests/unit/resource/test_continuous.json       | 12 ++++
 .../tests/unit/resource/test_discrete.json         | 16 +++++
 .../tests/integration/test_broker_starvation.json  | 20 ++++++
 .../integration/test_resource_backpressure.json    |  4 ++
 .../src/cascade/compiler/backend/builder.py        | 30 +++++----
 .../src/cascade/compiler/backend/validator.py      | 19 +-----
 .../compiler/backend/validator.stitcher.yaml       | 14 +++-
 .../tests/unit/backend/test_builder_environment.py |  6 +-
 .../cascade-std/src/cascade/std/probe/const.py     |  8 +--
 .../src/cascade/std/probe/const.stitcher.yaml      |  6 +-
 .../src/cascade/std/resource/discrete.py           | 10 ---
 .../cascade/std/resource/discrete.stitcher.yaml    |  7 +-
 .../src/cascade/std/resource/requestor.py          | 12 +---
 .../cascade/std/resource/requestor.stitcher.yaml   |  8 ++-
 .../cascade-std/src/cascade/std/triad/stainer.py   |  4 +-
 .../tests/integration/test_broker_starvation.py    | 75 +++++++++++-----------
 .../test_broker_starvation.stitcher.yaml           |  7 ++
 .../integration/test_resource_backpressure.py      | 44 +++++++------
 27 files changed, 256 insertions(+), 128 deletions(-)
```