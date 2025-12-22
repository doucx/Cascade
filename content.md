# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
cicd/tasks.py                                      |  9 +++-
 cicd/workflows.py                                  | 13 ++---
 packages/cascade-sdk/src/cascade/__init__.pyi      | 50 ++++++++++++++----
 packages/cascade-sdk/src/cascade/fs/__init__.pyi   |  3 +-
 packages/cascade-sdk/src/cascade/http/__init__.pyi | 40 +++++++++++---
 packages/cascade-sdk/src/cascade/io/__init__.pyi   |  3 --
 .../cascade-sdk/src/cascade/io/local/__init__.pyi  |  7 ++-
 .../cascade-sdk/src/cascade/io/s3/__init__.pyi     |  9 ++--
 .../cascade-sdk/src/cascade/io/stdin/__init__.pyi  |  3 +-
 .../cascade-sdk/src/cascade/io/stdout/__init__.pyi |  3 +-
 packages/cascade-sdk/src/cascade/ipfs/__init__.pyi |  4 +-
 packages/cascade-sdk/src/cascade/read/__init__.pyi |  5 +-
 .../cascade-sdk/src/cascade/write/__init__.pyi     |  5 +-
 scripts/generate_stubs.py                          | 61 +++++++++++++---------
 scripts/test_stubs.py                              | 12 +++--
 tests/cicd/test_tasks.py                           |  8 +--
 16 files changed, 153 insertions(+), 82 deletions(-)
```