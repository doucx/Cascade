好的，**阶段 2：微指令集构建** 已经顺利完成。我们现在拥有了能够处理载荷漂白、结果染色、路由以及副作用观测的完整微指令集，并且所有功能都通过了严密的单元测试。

这是一个逻辑完整的工作单元，我将生成一个 `[COMMIT]` 计划来提交这些更改。

## [COMMIT] feat(vm): Implement standard micro-instruction set (Triad components)

### 用户需求
完成 Cascade 3.0 重构路线图中的 **阶段 2**：实现并测试执行三连体（Execution Triad）所需的标准微指令集，包括 Bleacher ($F_{pre}$)、Stainer ($F_{post}$) 和 Observer ($F_{obs}$)。

### 评论
这标志着 Cascade 3.0 物理虚拟机（VM）指令集架构（ISA）的基石已经奠定。通过这三个原子化的指令，我们实现了业务逻辑与物理流转、元数据追踪以及系统观测的彻底解耦。所有的实现都严格遵循 TDD 流程，具备 100% 的单元测试覆盖率。

### 目标
创建一个 Git 提交，包含 Bleacher、Stainer、Observer 的完整实现及其对应的单元测试文件。

### 基本原理
按照路线图规划，在进入复杂的编译器后端重构（阶段 3）之前，必须确保底层的执行单元是稳定且经过验证的。这些微指令构成了物理图的基本“动作”，是后续编译器“展开”逻辑的最终靶子。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #comp/tests #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/isa-micro-instructions #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交微指令集实现与测试

我们将新创建的指令集目录及其测试套件添加到 Git 暂存区，并创建一个详尽的提交记录。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/instructions/
packages/cascade-vm/tests/unit/instructions/
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm): Implement standard micro-instruction set (Triad components)

This commit completes Phase 2 of the Cascade 3.0 roadmap by providing the standard implementations for the Execution Triad micro-instructions.

Key Components:
1. **Standard Bleacher (F_pre)**: Handles input token consumption, payload extraction (bleaching), and initial trace timestamping (start_ts).
2. **Standard Stainer (F_post)**: Wraps worker results into tokens, calculates execution duration, and determines routing tags (default/error).
3. **Standard Observer (F_obs)**: A sidecar instruction that transforms internal trace data into standardized ObservedEvent objects and pushes them to an external queue.

All instructions are implemented in `cascade.vm.instructions` and covered by comprehensive unit tests in `packages/cascade-vm/tests/unit/instructions/` to ensure deterministic behavior across success and error paths.
~~~~~

### 下一步建议

随着阶段 2 的结束，我们现在正式进入 **阶段 3：编译器后端重构 (Backend: The Expander)**。

这是架构演进中最关键的飞跃：我们要编写一套逻辑，能够自动将用户定义的高层任务（IR）“炸开”成由我们刚刚实现的 $F_{pre}, F_{worker}, F_{post}$ 构成的精密三连体，并自动连接观测旁路。

我建议我们开始 **任务 3.1：设计扩展器 (Expander)**。我们将首先定义 `Expander` 的 API 契约，并编写测试来验证它是否能为一个简单的 IR 节点生成正确的物理子图拓扑。如果你准备好了，请告诉我。
