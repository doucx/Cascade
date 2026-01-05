# 📸 Snapshot Capture

检测到工作区发生变更。

### 📝 变更文件摘要:
```
observatory/benchmarks/tco_performance.py          |  4 +-
 observatory/experiments/run_fireflies.py           |  2 +-
 .../src/cascade/app/__init__.py                    | 12 ++---
 .../tests/integration/test_telemetry_contract.py   |  4 +-
 .../tests/integration/test_resource_contention.py  |  2 +-
 .../tests/integration/test_static_integrity.py     |  4 +-
 .../src/cascade/providers/subflow.py               |  6 +--
 .../tests/integration/test_config.py               |  4 +-
 .../cascade-library/tests/integration/test_file.py |  4 +-
 .../tests/integration/test_helpers.py              |  6 +--
 .../cascade-library/tests/integration/test_http.py |  4 +-
 .../cascade-library/tests/integration/test_io.py   |  4 +-
 .../cascade-library/tests/integration/test_s3.py   |  4 +-
 .../tests/integration/test_signal_provider.py      |  4 +-
 .../cascade-library/tests/integration/test_sql.py  |  4 +-
 .../tests/integration/test_stdio.py                |  4 +-
 .../tests/integration/test_subflow.py              |  4 +-
 .../tests/integration/test_time_provider.py        |  4 +-
 .../tests/integration/test_ipfs.py                 |  6 +--
 .../src/cascade/adapters/cache/__init__.py         |  3 --
 .../src/cascade/adapters/cache/in_memory.py        | 23 ---------
 .../cascade/adapters/cache/in_memory.stitcher.yaml |  2 -
 .../src/cascade/adapters/cache/redis.py            | 34 -------------
 .../src/cascade/adapters/cache/redis.stitcher.yaml |  4 --
 .../src/cascade/adapters/caching/__init__.py       |  3 --
 .../src/cascade/adapters/caching/file_existence.py | 26 ----------
 .../adapters/caching/file_existence.stitcher.yaml  |  6 ---
 .../src/cascade/adapters/executors/__init__.py     |  3 --
 .../src/cascade/adapters/executors/local.py        | 57 ----------------------
 .../cascade/adapters/executors/local.stitcher.yaml |  6 ---
 ...
 192 files changed, 3701 insertions(+), 3726 deletions(-)
```