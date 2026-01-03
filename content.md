简要回答

好的，我们已经成功完成了 Cascade 3.3 架构演进路线图的第一阶段目标。现在我们将创建一个正式的提交，记录这一具有里程碑意义的架构演进。

## [COMMIT] feat(vm): establish foundation for Dual-Engine Symbiosis with Rust

### 用户需求
完成路线图定义的“接口硬化”、“数据纯化”、“测试基建改造”和“Rust 桥头堡建立”任务，并提交代码。

### 评论
这是一个重大的架构升级。我们不仅引入了 Rust 作为未来的高性能引擎，更重要的是，我们通过“接口硬化”和“参数化测试夹具”建立了一套可扩展、可验证的体系。这使得 Cascade 具备了“一套测试，双重验证”的能力，为后续的性能突击提供了坚实的安全网。

### 目标
创建一个 Git 提交，包含所有涉及接口协议、Runner 重构、根目录测试配置以及 Rust `cascade-vm-rs` 项目初始化和类型安全修复的代码。

### 基本原理
按照“先上锁，再加速”的战略，本次提交锁定了核心接口契约和测试基础设施。虽然 Rust 引擎目前仅是占位，但它标志着 FFI 链路的完全打通。

### 标签
#intent/architect #intent/build #flow/ready #priority/high #comp/vm #comp/vm-rs #comp/compiler #comp/tests #concept/ffi #concept/interface #scope/core #ai/instruct #task/domain/vm #task/object/dual-engine-symbiosis #task/action/architecture-evolution #task/state/end

---

### Script

#### Acts 1: 提交 Dual-Engine 演进的基础代码

我们将所有相关的修改添加到暂存区并执行提交。

~~~~~act
git_add
packages/cascade-vm/src/cascade/vm/protocols.py
packages/cascade-vm/src/cascade/vm/__init__.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-vm/tests/unit/test_reactor.py
packages/cascade-compiler/tests/integration/test_graph_purity.py
packages/cascade-compiler/src/cascade/compiler/utils/hashing.py
packages/cascade-common/src/cascade/common/context.py
packages/cascade-std/src/cascade/std/probe/context.py
conftest.py
packages/cascade-vm-rs/
pyproject.toml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(vm): establish foundation for Dual-Engine Symbiosis with Rust

This commit completes the initial phase of the Cascade 3.3 'Symbiosis' roadmap, 
establishing the architectural and infrastructure requirements for a high-performance 
Rust-based Reactor.

Key changes:
1. **Interface Hardening**: Defined `ReactorProtocol` in `cascade-vm` to decouple
   `EventDrivenRunner` from specific implementations, enabling dependency injection.
2. **Data Purification**: Introduced an automated graph purity audit in the 
   compiler tests to ensure `BipartiteGraph` remains a pure, serializable data 
   structure compatible with Rust FFI.
3. **Test Infra Upgrade**: Created a root-level `conftest.py` with a session-scoped 
   `reactor_backend_factory` fixture, allowing full test suite execution across 
   different backends via `--reactor-backend=[python|rust]`.
4. **Rust Bridgehead**: Initialized `cascade-vm-rs` using PyO3 0.23 (Python 3.13 
   compatible). Implemented a minimal `RustReactor` that satisfies the 
   protocol and successfully handles asynchronous FFI calls.
5. **Type Safety**: Resolved several potential null-access and attribute errors 
   identified by static analysis in hashing and context services.

This sets the stage for TDD-driven development of the Rust Reactor logic.
~~~~~

### 下一步建议

我们已经建立了完美的“脚手架”。接下来的核心挑战是**数据对齐**。

虽然我们已经确认了图是可序列化的，但 Rust 目前还无法真正“读取”它。我建议下一步的任务是：
1.  **定义 Rust 侧的数据模型**：在 `cascade-vm-rs` 中使用 `serde` 定义与 Python `BipartiteGraph` 对应的结构。
2.  **实现图转换器**：在 `RustReactor::new` 中，实现将传入的 PyObject（图）转换为 Rust 原生数据结构的逻辑。

这将让 Rust 引擎真正“看到”物理场的拓扑结构。
