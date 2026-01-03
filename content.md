# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../cascade-std/src/cascade/std/probe/context.json |  4 +--
 .../cascade-std/src/cascade/std/probe/env.json     |  4 +--
 .../cascade-std/src/cascade/std/probe/pulse.json   |  4 +--
 .../src/cascade/std/resource/continuous.json       | 10 ++++++
 .../src/cascade/std/resource/discrete.json         | 10 ++++++
 .../src/cascade/std/system/drainer.json            |  4 +--
 .../src/cascade/std/system/terminator.json         |  4 +--
 .../src/cascade/std/triad/bleacher.json            |  4 +--
 .../src/cascade/std/triad/observer.json            |  4 +--
 .../cascade-std/src/cascade/std/triad/stainer.json |  4 +--
 .../cascade-std/tests/unit/probe/test_context.json |  8 ++---
 .../cascade-std/tests/unit/probe/test_env.json     |  8 ++---
 .../cascade-std/tests/unit/probe/test_pulse.json   |  4 +--
 .../tests/unit/resource/test_continuous.json       | 14 +++++++++
 .../tests/unit/resource/test_discrete.json         | 18 +++++++++++
 .../tests/unit/system/test_drainer.json            |  4 +--
 .../tests/unit/system/test_terminator.json         |  4 +--
 .../tests/unit/triad/test_bleacher.json            | 16 +++++-----
 .../tests/unit/triad/test_observer.json            | 12 ++++----
 .../cascade-std/tests/unit/triad/test_stainer.json | 12 ++++----
 .../cascade-std/src/cascade/std/probe/pulse.py     |  4 ++-
 .../src/cascade/std/resource/__init__.py           |  2 +-
 .../src/cascade/std/resource/continuous.py         | 36 ++++++++--------------
 .../cascade/std/resource/continuous.stitcher.yaml  | 13 ++++++++
 .../src/cascade/std/resource/discrete.py           | 35 ++++++++-------------
 .../cascade/std/resource/discrete.stitcher.yaml    | 12 ++++++++
 .../cascade-std/src/cascade/std/triad/bleacher.py  |  4 ++-
 .../cascade-std/src/cascade/std/triad/stainer.py   |  4 ++-
 .../cascade-std/tests/unit/probe/test_context.py   |  2 +-
 packages/cascade-std/tests/unit/probe/test_env.py  |  2 +-
 ...
 38 files changed, 215 insertions(+), 157 deletions(-)
```