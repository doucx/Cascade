太棒了！测试通过标志着 Cascade 3.0 的物理引擎内核已经完全具备了处理复杂控制流和资源竞争的能力。我们已经成功从一个简单的顺序执行器演进为了一个真正的“全对称计算物理场”。

现在，我将生成一个 `[COMMIT]` 计划，将这些里程碑式的改动永久固化到代码库中。

## [COMMIT] feat(vm/compiler): 实现基于拓扑的控制流分支与资源背压

### 用户需求
在物理执行层实现白皮书定义的“全对称”控制逻辑：
1.  **条件分支**: 通过通道的光谱过滤（Tag Filtering）实现。
2.  **并发控制**: 通过物理拓扑中的资源令牌闭环（Resource Back-pressure）实现。

### 评论
这是 Cascade 3.0 重构路线图中最重要的架构里程碑。我们不仅实现了一个高性能的计算引擎，更实现了一种“逻辑即拓扑”的哲学转变。通过将复杂的并发和条件逻辑解构为简单的令牌流动和光谱过滤，我们极大地降低了引擎的复杂性，同时获得了近乎无限的可观测性和可扩展性。

### 目标
创建一个完整的 Git 提交，包含物理层、编译器层和微指令层的协同升级，以及所有验证这些核心物理特性的测试用例。

### 基本原理
此提交将 Phase 4 的所有成果整合为一个逻辑单元。它确立了物理节点间交互的具名端口协议，实现了 `Reactor` 的原子化扫描机制，并为编译器注入了自动化资源编排的能力。这些改动共同构成了 Cascade 3.0 的“物理定律”。

### 标签
#intent/build #flow/ready #priority/high #comp/vm #comp/compiler #comp/spec #concept/control-flow #concept/resources #scope/core #ai/instruct #task/domain/core #task/object/physics-field #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 提交全对称物理场核心实现

我们将所有涉及 Spec、VM、Compiler 以及新测试用例的文件添加到暂存区并提交。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/topology.py
packages/cascade-spec/src/cascade/spec/physics.py
packages/cascade-spec/src/cascade/spec/ir/models.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-vm/src/cascade/vm/reactor.py
packages/cascade-vm/src/cascade/vm/instructions/bleacher.py
packages/cascade-vm/src/cascade/vm/instructions/stainer.py
packages/cascade-vm/tests/integration/test_ping_pong.py
packages/cascade-vm/tests/integration/test_branching.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-vm/tests/unit/test_reactor.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm/compiler): Implement topological control flow and resource back-pressure

This commit implements the "Fully Symmetric Computational Physics Field" as defined in the 3.0 Whitepaper. 

Key architectural changes:
1.  **Channel Tag Filtering (The Prism)**: Upgraded the Reactor to support spectrum filtering. Channels now act as physical barriers that only allow tokens with matching tags to pass, enabling topological branching (run_if, switch) without centralized logic.
2.  **Resource Back-pressure (The Loop)**: Implemented topological resource management. Bleacher nodes now "acquire" resource tokens from global ResourceSlots (D_res), and Stainer nodes "release" them back upon completion. This enables decentralized concurrency control via the graph's geometry.
3.  **Atomic Reactor Scanning**: Refactored the Reactor's step logic to use an "Atomic Scan & Consume" model. This eliminates TOCTOU race conditions when multiple nodes compete for shared resources, ensuring deterministic execution.
4.  **Named Port Protocol**: Standardized physical node I/O to use named ports and Token dictionaries. This removes positional ambiguity and enables complex multi-port emission (e.g., results + resource returns + observability signals).

Verified via:
- test_branching.py: Confirmed tokens are physically blocked by mismatched tag filters.
- test_resource_backpressure.py: Confirmed sequential execution when shared resource tokens are limited.
- test_ping_pong.py: Updated to comply with the new multi-port protocol.
~~~~~

### 下一步建议
随着 **Phase 4** 的圆满完成，Cascade 3.0 的核心“发动机”已经打造完毕。

下一步，我们将进入 **Phase 5: 全系统集成 (System Integration)**。在这个阶段，我们将：
1.  **完善编译器**: 让 `Builder` 能够处理字面量输入（Literals），从而无需手动注入测试 Token。
2.  **前端对接**: 将 `LazyResult` 的 DSL 逻辑与 `Compiler` 后端正式打通。
3.  **端到端闭环**: 实现一个统一的 `cs.run()` 接口，让用户在完全感知不到底层物理场的情况下，享受其带来的高性能和高可靠性。

如果你准备好了，我们可以先从 `Builder` 的字面量支持开始。
