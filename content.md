# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/app/__init__.json                  |  1 -
 .../src/cascade/graph/analysis/protocols.json      | 10 +++++
 .../src/cascade/graph/analysis/reflection.json     | 18 +++++++++
 .../cascade-graph/src/cascade/graph/hashing.json   | 19 +++------
 .../cascade-graph/src/cascade/graph/model.json     |  6 +--
 .../cascade-graph/tests/test_serialize.json        |  8 ++--
 .../src/cascade/providers/registry.json            | 11 ------
 .../packages/cascade-sdk/src/cascade/testing.json  | 19 +++++++++
 .../cascade-sdk/src/cascade/tools/events.json      |  6 ---
 .../cascade-spec/src/cascade/spec/fingerprint.json | 46 ++++++++++++++++++++++
 .../cascade-spec/src/cascade/spec/ir/models.json   | 11 ++++++
 .../cascade-spec/src/cascade/spec/task.json        |  1 -
 .../src/cascade/graph/analysis/protocols.py        | 17 +-------
 .../cascade/graph/analysis/protocols.stitcher.yaml | 11 ++++++
 .../src/cascade/graph/analysis/reflection.py       |  8 ----
 .../graph/analysis/reflection.stitcher.yaml        |  5 +++
 .../cascade-graph/src/cascade/graph/hashing.py     | 11 ------
 .../src/cascade/graph/hashing.stitcher.yaml        | 12 +++++-
 .../tests/test_serialize.stitcher.yaml             |  2 -
 packages/cascade-sdk/src/cascade/testing.py        |  5 ---
 .../cascade-sdk/src/cascade/testing.stitcher.yaml  |  3 ++
 .../cascade-spec/src/cascade/spec/ir/models.py     | 16 --------
 .../src/cascade/spec/ir/models.stitcher.yaml       | 10 +++++
 tests/e2e/runtime/harness.py                       |  3 +-
 24 files changed, 159 insertions(+), 100 deletions(-)
```