简要回答：
好的，我们将增强的观测指标提交，以提高仿真的可解释性。

## [COMMIT] feat(exp): 增强萤火虫观测性，显示原始 Flash 计数

### 用户需求
在多核并行仿真中，将原始的 Agent 闪烁计数（`_flash_count`）添加到状态栏，以解释高层指标 `Pulse` (周期数) 的跳跃式增长现象。

### 评论
这个改进将系统行为的可观测性提高了一个层次。通过暴露底层数据，我们让用户能够清楚地理解异步、多速率系统中，低频采样器（Monitor）是如何处理高频事件流的，避免了指标跳跃带来的误解。

### 目标
提交 `run_fireflies.py` 中对 `monitor_callback` 的修改，增加 `Flashes` 字段。

### 基本原理
持续遵循提高开发者体验（DX）和可观测性的原则，使复杂的底层行为对用户透明。

### 标签
#intent/tune #flow/ready #priority/medium #comp/experiments #scope/dx #concept/observability #ai/instruct #task/domain/experiments #task/object/ui-enhancement #task/action/enhancement #task/state/end

---

### Script

#### Acts 1: 提交观测性增强

提交对 `run_fireflies.py` 的修改。

~~~~~act
git_add
observatory/experiments/run_fireflies.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(exp): display raw flash count in firefly monitor for better observability

The convergence monitor's 'Pulse' count is derived from total flashes, leading to jumpy updates due to the monitor's low sampling rate (2Hz).

This change adds the raw, total flash count ('Flashes') to the status bar. This provides users with direct visibility into:
1. The extreme high-frequency nature of the underlying agent simulation.
2. The reason for the step-wise updates of the 'Pulse' metric, clarifying that missing numbers are due to low-frequency observation, not simulation errors.
~~~~~

### 下一步建议
我们已经完成了多核并行、VM 治理以及可观测性的基础建设。下一步可以开始探索你提出的**“跨进程 Agent 通信”**问题，即实现一个分布式连接器，连接这些在不同核心上运行的“同步孤岛”，将仿真升级为真正的分布式网格。
