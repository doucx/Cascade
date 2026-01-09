好的，既然所有测试已经通过，我们现在完成了 **Cascade 物理接口定义层 (PIDL)** 路线图的全部四个阶段。

这是一个重大的架构升级，它确立了物理层接口的强类型契约，消除了系统中的魔法字符串。

## [COMMIT] feat: Implement Physical Interface Definition Layer (PIDL) across Spec, Std, and Compiler

### 用户需求
实施完整的 PIDL 路线图，消除物理层中的硬编码端口名，建立强类型的单一事实来源 (SSoT) 契约体系。

### 评论
PIDL 的实施彻底解决了“接口漂移”问题。通过将物理定律（PhysicsSpec）、标准契约（Std Specs）和执行逻辑（Kernels）统一到同一个声明式框架下，我们让 Cascade 的架构达到了“物理上正确”的高度。Compiler 现在不再是盲目地拼接字符串，而是根据明确定义的契约来构建物理世界的拓扑结构。

### 目标
1.  **建立物理法则**: 在 `cascade-spec` 中实现了 `PhysicsSpec` 和 `Port` 体系，支持静态和动态端口定义。
2.  **标准化契约**: 在 `cascade-std` 中定义了所有核心 IC（Bleacher, Worker, Stainer, Allocator, Egress 等）的 Specs。
3.  **重构内核**: 引入了 `@implements(Spec)` 装饰器和高性能的 `IOWrapper` 视图，实现了内核函数的零拷贝、类型化访问。
4.  **重构编译器**: 全面重构了编译器的 `Wiring Policies` 和 `Expander`，移除 `PortName` 类，所有连线均引用自 Spec。

### 基本原理
我们采用了“类声明式 Spec 模式”，利用 Python 元类自动提取端口定义。这使得接口既是可执行的代码，也是自文档化的定义。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/std #comp/compiler #scope/core #ai/delegate #task/domain/architecture #task/object/pidl-roadmap #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交 PIDL 完整实施内容

我们将把涉及 Spec 定义、标准库契约、内核重构以及编译器连线修改的所有文件添加到暂存区。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/physics/
packages/cascade-spec/src/cascade/spec/physical/ports.py
packages/cascade-std/src/cascade/std/specs/
packages/cascade-std/src/cascade/std/kernel_tools.py
packages/cascade-std/src/cascade/std/triad/bleacher.py
packages/cascade-std/src/cascade/std/triad/stainer.py
packages/cascade-std/src/cascade/std/resource/discrete.py
packages/cascade-std/src/cascade/std/resource/requestor.py
packages/cascade-std/src/cascade/std/system/egress.py
packages/cascade-std/src/cascade/std/system/gate.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/pulse.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/observability.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/control.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/policies/parameter.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/prisms/discrete.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: Implement Physical Interface Definition Layer (PIDL)

This architectural milestone eliminates "magic strings" in the physical layer by establishing a strong-typed, single source of truth (SSoT) for physical node interfaces.

Key Achievements:
1.  **PhysicsSpec (cascade.spec.physics)**: Introduced a declarative DSL for defining physical port contracts. Supports Port.Input, Port.Output, MapInput, and MapOutput with prefix-based dynamic routing.
2.  **Standard Contracts (cascade.std.specs)**: Formalized interfaces for all core components (Triad, Resource Brokers, System ICs) using PhysicsSpec, decoupling topology from implementation.
3.  **Kernel Evolution (@implements)**: Refactored kernel functions in cascade-std to use the @implements decorator. It utilizes a zero-copy IOWrapper to provide typed attribute access (io.port_name) to underlying token dictionaries, ensuring runtime compliance with Specs.
4.  **Compiler Rewiring**: Updated all Wiring Policies (Pulse, Observability, ControlFlow, Parameter, Resource) to depend exclusively on Spec attributes.
5.  **Axiom Enforcement**: Deleted the deprecated PortName constant class, forcing all future development to adhere to the PIDL contract system.

This transition ensures that the physical world (compiled graph) is an exact, verifiable projection of the logical intent, drastically reducing protocol drift and enhancing system observability.
~~~~~

### 下一步建议
我们已经完成了 PIDL 的基础建设。由于物理图现在是完全同构且结构清晰的，下一步建议开启 **阶段五：物理层优化 (Physics Optimization)**，包括：
- **算子融合 (Node Fusion)**: 利用 Spec 信息自动合并简单的 F-D-F 链路。
- **常量折叠 (Constant Folding)**: 在编译时预填已知常量的 D 节点。
- **JIT 调度优化**: 减少 Reactor 在处理高频、无副作用节点时的调度开销。
