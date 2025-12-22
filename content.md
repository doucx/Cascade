# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
packages/cascade-engine/src/cascade/__init__.py    |  2 +-
 .../src/cascade/runtime/constraints/handlers.py    |  4 +-
 packages/cascade-graph/src/cascade/__init__.py     |  2 +-
 packages/cascade-library/src/cascade/__init__.py   |  2 +-
 packages/cascade-sdk/src/cascade/__init__.pyi      | 45 ++++++++++++++++++----
 packages/cascade-sdk/src/cascade/http/__init__.pyi | 37 +++++++++++++++---
 packages/cascade-sdk/src/cascade/io/__init__.pyi   |  1 -
 .../cascade-sdk/src/cascade/io/local/__init__.pyi  |  4 +-
 .../cascade-sdk/src/cascade/io/s3/__init__.pyi     |  6 ++-
 packages/cascade-sdk/src/cascade/ipfs/__init__.pyi |  1 +
 packages/cascade-sdk/src/cascade/read/__init__.pyi |  2 +-
 .../cascade-sdk/src/cascade/write/__init__.pyi     |  2 +-
 packages/cascade-spec/src/cascade/__init__.py      |  2 +-
 scripts/generate_stubs.py                          |  8 ++--
 tests/engine/e2e/test_e2e_robustness.py            |  6 +--
 15 files changed, 90 insertions(+), 34 deletions(-)
```