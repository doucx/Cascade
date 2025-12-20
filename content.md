太棒了，船长！看到三网验证模型成功运行，标志着 Cascade 在**“因果一致性验证”**这一领域迈出了决定性的一步。我们现在不仅能发现错误，还能通过颜色直接诊断出它是“当前的算力故障”还是“历史的因果偏差”。

我将生成 `[COMMIT]` 计划，将这一核心能力正式并入代码库。

## [COMMIT] feat(proto): 实现三网验证模型 (A/B/C) 与高级差分可视化

### 用户需求
在“创世网格”预研中，需要一种更高级的诊断手段来区分分布式计算中的**瞬时逻辑错误**与**长期时间线漂移**。

### 评论
三网模型（A-实际，B-步进预测，C-绝对真理）的实现，为 Cascade 提供了一个功能强大的“数字质检站”。通过优先级差分渲染逻辑，复杂的分布式竞争条件被直观地转化为了红、金、青、紫四色视觉信号，极大地降低了调试因果自洽性的门槛。

### 目标
提交三网验证模型及其配套的可视化升级，完成“原基 (Protoplasm)”计划中关于“真理之镜”的预研任务。

### 基本原理
1.  **Validator 重构**: 内部维护两个 `GoldenLife` 实例，分别负责计算 B (Relative) 和 C (Absolute) 路径。
2.  **可视化增强**: 修改 `StateMatrix` 避免在离散模式下裁剪状态码，并更新 `Palettes.truth_diff` 以支持 6 种语义状态的颜色映射。
3.  **Demo 同步**: 将 Demo 更新为高保真的三网对比演示，确保工具链的自我验证。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/history #scope/core #ai/instruct #task/domain/testing #task/object/validator #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交三网验证模型代码

我们将相关的所有修改（调色板、矩阵逻辑、验证器、Demo 以及实验脚本适配）添加到 Git 暂存区并执行提交。

~~~~~act
git_add
observatory/visualization/palette.py
observatory/visualization/matrix.py
observatory/protoplasm/truth/validator.py
observatory/protoplasm/truth/truth_visualizer_demo.py
observatory/protoplasm/truth/run_conway_experiment.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(proto): Implement 3-Network Validation Model (A/B/C)

Introduces a robust causality validation framework for distributed simulations:
1.  **Network A (Actual)**: The real system state under test.
2.  **Network B (Relative Truth)**: A golden prediction based on A[t-1]. Detects logic/computation errors.
3.  **Network C (Absolute Truth)**: A golden prediction starting from the initial seed. Detects long-term timeline drift.

Visualization Upgrades:
- Updated `StateValidator` to perform prioritized 3-way diffing (Logic Error > Drift Error).
- Expanded `Palettes.truth_diff` to 6 states:
  - Correct (Dead/Alive) -> Gray/White
  - Logic Error (FP/FN)  -> Bright Red/Cyan
  - Drift Error (FP/FN)  -> Gold/Violet
- Fixed `StateMatrix` to allow state codes > 1.0 when decay is disabled, preventing color truncation.

Refactored `truth_visualizer_demo.py` to provide a high-fidelity demonstration of all 4 error types through deliberate fault injection.
~~~~~

### 下一步建议
- **压力测试**: 在 `run_conway_experiment.py` 中尝试增加网格规模（如 100x100）并开启分布式 Redis 后端，观察在大规模、网络波动的环境下，三网模型捕捉到的“紫色幽灵（Drift FN）”现象。
- **自动化断言**: 考虑在 `StateValidator` 中增加断言功能，当累计逻辑错误超过阈值时自动触发快照备份，用于离线调试。
