好的，我们已经完成了采样芯片 (Probe ICs) 和系统主权芯片 (System ICs) 的实现及其单元测试。现在我将生成一个 `[COMMIT]` 计划，将这些新功能正式提交。

## [COMMIT] feat(std): 实现标准采样芯片与系统主权芯片

### 用户需求
执行 `Act 0.5` 路线图中的任务 T3 和 T5，在 `cascade-std` 中提供探测外部环境（参数、环境变量）的能力，以及图内部控制生命周期（HALT, DRAIN）的能力。

### 评论
这次提交为 Cascade 3.0 引入了关键的“外感知”和“自决权”能力。`Probe ICs` 允许计算图不再是封闭的孤岛，而是能主动感应外部上下文；`System ICs` 则将控制流彻底拓扑化，让图通过发射特殊令牌来宣告自身的终结。这完善了“主权图”模型的物理基础。

### 目标
1. 提交 `cascade-spec` 中关于 `SystemControlToken` 的新定义。
2. 提交 `cascade-std/probe` 下的 `ParamProbe`、`EnvProbe` 和 `PulseGenerator` 实现。
3. 提交 `cascade-std/system` 下的 `terminator` (HALT) 和 `drainer` (DRAIN) 实现。
4. 提交上述所有芯片的配套单元测试。

### 基本原理
我们遵循 IC 原子化设计原则：每个芯片仅负责单一的物理转换逻辑。通过在 `cascade-spec` 中统一定义 `SystemControlToken`，我们确保了控制信号在整个物理场中的语义一致性。单元测试验证了这些芯片在各种输入条件下的输出确定性。

### 标签
#intent/build #flow/ready #priority/high #comp/std #comp/spec #concept/sovereignty #scope/core #ai/instruct #task/domain/architecture #task/object/standard-ics #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 提交探测与控制功能

我们将新创建的芯片代码、规范定义及测试文件添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/system.py
packages/cascade-std/src/cascade/std/probe/
packages/cascade-std/tests/unit/probe/
packages/cascade-std/src/cascade/std/system/
packages/cascade-std/tests/unit/system/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(std): implement Probe and System ICs

Expanded the standard physics library with sampling and lifecycle control capabilities.

Key Features:
1. **Probe ICs**:
   - `param_probe`: Samples values from the global WorkflowContext.
   - `env_probe`: Samples OS environment variables.
   - `pulse_generator`: Acts as a sync pulse multiplier for energy distribution.
2. **System ICs (Sovereignty)**:
   - `halt_signal`: Generates SIG_HALT to request immediate Reactor shutdown.
   - `drain_signal`: Generates SIG_DRAIN for graceful branch termination.
3. **Spec Update**: Defined `SystemControlToken` in cascade-spec as a universal control signal carrier.
4. **Testing**: Comprehensive unit tests for all new ICs ensuring deterministic behavior.

This fulfills Tasks T3 and T5 of the Act 0.5 Foundry roadmap.
~~~~~

### 下一步建议
我们已经完成了大部分外围芯片的建设。

现在到了 Act 0.5 最核心、最硬核的挑战：**任务 T4: 实现资源经纪人芯片 (Resource Broker ICs)**。
这涉及到如何用纯物理拓扑解决浮点数资源管理（例如 5.1GB 内存）以及当资源不足时如何利用物理背压挂起 Token。

如果你准备好了，我们将开始攻克这个难关。
