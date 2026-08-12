# 📸 Snapshot Capture

### 💬 备注:
ruff

检测到工作区发生变更。

### 📝 变更文件摘要:
```
README.md                                          |  6 ++--
 archive/observatory/debug/debug_01_bus.py          |  1 +
 archive/observatory/debug/debug_02_single_agent.py |  2 ++
 cicd/main.py                                       |  2 ++
 cicd/tasks.py                                      | 12 +++++---
 cicd/tests/test_tasks.py                           |  4 +--
 cicd/workflows.py                                  | 11 ++++---
 conftest.py                                        | 15 ++++-----
 docs/concepts/control_vs_data_flow.md              |  8 ++++-
 docs/how-to-guides/advanced-workflows.md           | 36 ++++++++++++++--------
 docs/how-to-guides/defining-computations.md        |  8 +++--
 docs/how-to-guides/dependency-injection.md         |  8 ++++-
 docs/how-to-guides/improving-robustness.md         | 10 +++---
 docs/how-to-guides/using-providers.md              |  9 ++----
 docs/reference/cli-tools.md                        |  7 +++--
 docs/tutorial/getting-started.md                   |  4 +--
 examples/dump_physical_graph.py                    |  8 ++---
 migrations/002_restructure_runtime.py              |  1 +
 migrations/003_restructure_spec.py                 |  1 +
 migrations/004_migrate_execution_graph.py          |  1 +
 migrations/004_restructure_compiler_wiring.py      |  1 +
 observatory/agents/kuramoto.py                     |  8 +++--
 observatory/benchmarks/tco_performance.py          |  3 +-
 observatory/experiments/run_fireflies.py           | 28 +++++++++--------
 observatory/monitors/aggregator.py                 |  5 +--
 observatory/monitors/convergence.py                | 10 +++---
 observatory/networking/direct_channel.py           |  7 +++--
 observatory/networking/ipc.py                      |  9 ++++--
 observatory/protoplasm/agents/conway.py            | 15 +++++----
 .../protoplasm/governance/bottleneck_sim.py        |  7 +++--
 ...
 337 files changed, 2070 insertions(+), 1725 deletions(-)
```