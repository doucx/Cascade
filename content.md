好的，我将为新增的日志分析脚本创建提交。

## [COMMIT] feat(tooling): 添加日志相关性分析脚本

### 用户需求
将 `observatory/scripts/requirements.txt` 和 `observatory/scripts/analyze_logs.py` 文件提交到 Git 仓库，作为一个逻辑完整的工作单元。

### 评论
这个分析脚本是一个重要的里程碑。它不仅实现了用户对日志分析的直接需求，更重要的是，它展示了如何优雅地将 Cascade 的声明式工作流与传统数据科学工具链（如 Pandas）结合，从而实现复杂的数据处理和报告流程。这个工具将成为我们未来进行性能调优和验证分布式系统假设的核心资产。

### 目标
提交 `analyze_logs.py` 及其依赖项，并附上清晰的 Git 提交信息。

### 基本原理
我们遵循 `d3-constraint-quipu-plan-script-rules` 的原则，将文件创建与提交操作分离开来。由于文件已在上一阶段创建，现在可以在一个独立的 `[COMMIT]` 计划中完成提交操作。

### 标签
#intent/build #flow/ready #priority/medium #comp/tooling #scope/dx #ai/instruct #task/domain/tooling #task/object/log-analyzer #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 添加并提交文件

将新创建的分析脚本及其依赖文件添加到暂存区，并创建一个内容详尽的提交。

~~~~~act
git_add
observatory/scripts/requirements.txt
observatory/scripts/analyze_logs.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(tooling): Add log correlation analysis script

This commit introduces a new script, `analyze_logs.py`, built using Cascade's
declarative API and the Typhoeus CLI generator.

The script serves as a foundational tool for:
1. Loading nested JSONL logs (e.g., performance telemetry) using Pandas.
2. Flattening the metrics and calculating the correlation matrix.
3. Outputting a structured report to verify performance hypotheses (e.g., the strong negative correlation between `fps_min` and `flush_duration_ms_avg`).

This formalizes our ability to use data analysis within the Cascade ecosystem to
verify performance hypotheses.
~~~~~

### 下一步建议

现在我们已经证明了大规模同步带来的性能瓶颈，并有了工具来衡量它。根据 `CS-DOC-GENESIS-V2-CALIBRATION` 中的校准路线图，下一步我们应该开始 **战役 I (规模化与全彩渲染)** 的关键优化步骤：

**战役 I，步骤 1.2: 邻居发现优化**

当前 `conway.py` 中的 `collect_neighbors` 任务和 `run_fireflies.py` 中的 Agent 模式都依赖于 **通配符订阅** 或 **大量精确订阅**。在 Agent 数量达到 2500+ 时，这会造成巨大的消息风暴和 `LocalBus` 的性能损耗。

我建议将焦点转向：

1.  **重构 `conway_agent` 核心逻辑**，使其不再依赖 `collect_neighbors` 这种通配符订阅模式，而是显式订阅其 8 个邻居的 Topic。
2.  **验证 `LocalBus` 的优化效果**，确保它在精确订阅模式下表现高效。

你是否同意开始实施 **战役 I，步骤 1.2**？
