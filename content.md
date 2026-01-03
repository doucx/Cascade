好的，第一阶段到第三阶段的重构已经圆满完成。我们成功地将 `Builder` 从一个硬编码的单体逻辑演进为一个模块化的、基于策略和棱镜（Prism）的通用布线系统，并且确立了“主权端口”这一核心物理准则。

我将生成一个 `[COMMIT]` 计划来记录这一重要的架构里程碑。

## [COMMIT] refactor(compiler): 实施通用布线算法与主权端口体系

### 用户需求
将编译器后端重构为基于策略模式的通用布线算法，并实现主权端口（Sovereign Ports）模型，以支持资源的插拔式扩展和显式的分支路由。

### 评论
这是一次深度的架构“排毒”。我们移除了一直以来潜伏在物理图中的“隐式契约”（如对 `Token.tag` 的依赖和硬编码的资源拓扑），代之以纯粹的、显式的物理定律。这为 Cascade 未来的 JIT 优化、分布式扩展和复杂控制流（如 Jump 和分布式事务）铺平了道路。

### 目标
提交所有涉及编译器重构、策略拆分、资源系统解耦以及主权端口实施的代码。

### 基本原理
*   **通用布线算法**: 通过 `WiringPolicy` 链条，使布线过程变为可观测、可扩展的流水线。
*   **主权端口**: 将路由决策权从通道交还给节点，实现了拓扑的完全确定性（Topological Honesty）。
*   **资源棱镜**: 实现了资源类型与布线逻辑的解耦。

### 标签
#intent/refine #flow/ready #priority/high #comp/compiler #comp/std #comp/spec #concept/topology #concept/resource #scope/core #ai/delegate #task/domain/compiler #task/object/wiring-algorithm #task/action/refactor #task/state/end

---

### Script

#### Acts 1: 提交重构成果

我们将所有修改和新增的文件添加到 Git 暂存区，并创建一个内容详尽的提交记录。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/environment.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/tests/unit/triad/test_stainer.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/wiring/context.py
packages/cascade-compiler/src/cascade/compiler/wiring/protocol.py
packages/cascade-compiler/src/cascade/compiler/wiring/__init__.py
packages/cascade-compiler/src/cascade/compiler/wiring/prism.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/control.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/pulse.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/observability.py
packages/cascade-compiler/src/cascade/compiler/wiring/policies/resource.py
packages/cascade-compiler/src/cascade/compiler/wiring/prisms/discrete.py
packages/cascade-compiler/tests/unit/backend/test_expander.py
packages/cascade-compiler/tests/unit/test_sovereignty.py
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(compiler): implement universal wiring algorithm with sovereign ports

This commit marks a major architectural evolution of the Cascade compiler, moving away from a monolithic, hard-coded Builder to a modular, policy-based "Universal Wiring Algorithm".

Key Changes:

1. **Infrastructure Decoupling**: Introduced `WiringContext` and `WiringPolicy` protocol. The `Builder` is now a strategy engine that executes a pipeline of policies (Parameter, ControlFlow, Resource, Observability, Pulse).

2. **Declarative Resource System**: Refactored resource wiring to use the "Prism" pattern. Physical topology generation for resources is now encapsulated in `ResourcePrism` implementations (e.g., `DiscreteResourcePrism`). This allows adding new resource types without modifying the compiler core.

3. **Sovereign Ports**: Implemented the "Sovereignty of Egress" principle.
   - Deprecated the generic 'output' port in favor of explicit 'output_default' and 'output_error' ports.
   - Updated `standard_stainer` and `Expander` to generate and route to these sovereign ports.
   - This removes the hidden metadata contract between nodes and channels, moving routing logic back into the node's sovereign domain.

4. **Robust Parameter Mapping**: Enhanced `ParameterWiringPolicy` to correctly map logical positional indices ("0", "1") from IR to physical named ports on the Bleacher.

5. **Test Suite Modernization**: Updated unit and integration tests to align with the new port naming and modular architecture.

This refactoring ensures that the physical graph is a faithful, non-ambiguous projection of the logical intent, fulfilling the "Logic as Topology" axiom.
~~~~~

### 下一步建议
我们已经拥有了一个极其稳固且模块化的编译器后端。
根据[路线图](../../20_领域/Cascade/01_current/Cascade%203.1%20架构演进路线图：主权物理场.md)，接下来的逻辑终点是：
1.  **完善异常路由**: 修改 `standard_stainer` 使其在捕获异常时主动路由到 `output_error`。
2.  **JIT 优化阶段**: 既然物理图现在已经“完全保真”（甚至有些冗余），我们可以开始实现 `JIT` 或 `Compressor` 来消除三连体内部的中间节点开销，提升执行效率。

你希望先完善异常路由的闭环，还是进入 JIT 优化阶段？
