# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
.../src/cascade/test_utils/helpers.json            | 43 ++++++++++++++++------
 packages/cascade-sdk/src/cascade/fs/__init__.py    |  0
 packages/cascade-sdk/src/cascade/http/__init__.py  |  0
 packages/cascade-sdk/src/cascade/io/__init__.py    |  0
 .../cascade-sdk/src/cascade/io/local/__init__.py   |  0
 packages/cascade-sdk/src/cascade/io/s3/__init__.py |  0
 .../cascade-sdk/src/cascade/io/stdin/__init__.py   |  0
 .../cascade-sdk/src/cascade/io/stdout/__init__.py  |  0
 packages/cascade-sdk/src/cascade/ipfs/__init__.py  |  0
 .../cascade-sdk/src/cascade/providers/__init__.py  |  3 --
 .../src/cascade/providers/registry.stitcher.yaml   |  0
 packages/cascade-sdk/src/cascade/read/__init__.py  |  0
 .../cascade-sdk/src/cascade/testing.stitcher.yaml  | 36 ------------------
 packages/cascade-sdk/src/cascade/write/__init__.py |  0
 .../src/cascade/test_utils/helpers.stitcher.yaml   | 36 ++++++++++++++++++
 pyproject.toml                                     |  1 -
 16 files changed, 67 insertions(+), 52 deletions(-)
```