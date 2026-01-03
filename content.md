好的，我们已经完成了 Compiler 对控制流和序列依赖的基础设施构建。现在，我将生成一个 `[COMMIT]` 计划，将这些变更作为 Phase 2 的一个重要里程碑提交。

## [COMMIT] feat(compiler): 增强 Frontend 与 Backend 以支持控制流和序列依赖

### 用户需求
完善编译器，使其能够解析并物理化 `LazyResult` 的 `run_if` (条件执行) 和 `after` (序列依赖) 构造。

### 评论
通过这次更新，Cascade 的编译器从仅支持单纯的数据流 (Data-flow) 演进为能够支持复杂的控制流和时序逻辑。这标志着 Phase 2 (Compiler Intelligence) 的核心任务已基本完成。我们将逻辑上的控制信号映射为物理层 `Bleacher` 节点的 `SIGNAL` 输入，从而在不破坏物理层通用性的前提下，实现了高级语言特性的物理拓扑化。

### 目标
创建一个 Git 提交，包含对 `NodeIR` 模型、`HashingService`、`IRGenerator`、`Expander` 以及 `Builder` 的所有相关修改。

### 基本原理
这些修改构成了一个完整的、互相关联的逻辑单元：
1.  **定义层**: `NodeIR` 增加了对条件和依赖的感知能力。
2.  **身份层**: `HashingService` 确保了控制流路径的变更会导致节点 ID 的改变，符合 Hashlife 对确定性的要求。
3.  **解析层**: `IRGenerator` 实现了递归遍历和信息提取。
4.  **物理层**: `Expander` 和 `Builder` 协同将这些逻辑字段展开为物理场中的 `SIGNAL` 通道，完成了从“代码逻辑”到“物理拓扑”的最后跳跃。

### 标签
#intent/build #flow/ready #priority/high #comp/compiler #comp/spec #concept/control-flow #scope/core #ai/instruct #task/domain/compiler #task/object/control-flow-infrastructure #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交编译器对控制流的支持

我们将涉及 Spec 修改和 Compiler 内部逻辑修改的所有文件添加到暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/ir/models.py
packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
packages/cascade-compiler/src/cascade/compiler/frontend/generator.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(compiler): support run_if and explicit dependencies (after)

Enhances the compiler infrastructure to handle non-data dependencies, bridging the gap between high-level declarative constructs and low-level physical topology.

Key changes:
1. **NodeIR Update**: Added 'condition' and 'dependencies' fields to capture control-flow metadata in the logical graph representation.
2. **Hashing Service**: Updated the instance hash calculation to include IDs of condition and dependency nodes. This ensures that changes in the control-flow structure lead to unique node identities, essential for caching and structural reuse.
3. **Frontend (IRGenerator)**: Implemented recursive traversal for lr._condition and lr._dependencies, ensuring all prerequisite nodes are visited and correctly mapped to the NodeIR.
4. **Backend (Expander & Builder)**:
   - Expander now dynamically generates SIGNAL-role ports on the Bleacher node based on the NodeIR metadata.
   - Builder wires these ports to the Stainer's 'output' port of the respective upstream nodes, effectively physicalizing 'wait' and 'conditional' logic as topological channels.

This work completes a major milestone in Phase 2 of the Cascade 3.0 migration.
~~~~~

### 下一步建议
我们已经完成了编译器的“智能化”改造。现在是时候进入 **Phase 3：引擎的脑叶切除 (Engine Lobotomy)** 了。

由于 `Reactor`、`Memory` 和 `Compiler` 已经就绪，下一步的最佳行动是：
- **实现 `VMExecutionStrategy`**: 创建一个新的执行策略，它将作为旧 `Engine` 的核心替换方案。它的职责是调用 `IRGenerator` -> `Builder` 产出物理图，然后启动 `Reactor` 并监听 `Result Sink`。
- **验证集成**: 编写一个涵盖 `run_if`、`after` 和 `with_constraints` 的端到端测试，确保从 SDK 到 VM 的全链路已经跑通。
