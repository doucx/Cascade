太棒了！所有测试通过意味着我们已经成功完成了 Cascade 3.0 架构演进中最关键的一环：**链接协议 (The Linker Protocol)**。

我们现在正式确立了“编译器生产 Assembly，运行时链接并执行”的工业级模型。我将生成一个 `[COMMIT]` 计划，将这一里程碑式的改进永久记录在仓库中。

## [COMMIT] feat: 实现 Cascade 3.0 Assembly 与链接协议 (The Linker Protocol)

### 用户需求
按照实施路线图，完成从“单体编译执行”到“编译-链接-执行”分层架构的转型。

### 评论
这是 Cascade 3.0 走向成熟的重要里程碑。通过引入 `Assembly` 和 `Linker`，我们彻底解决了分布式环境下代码身份识别的难题，移除了 `VMExecutionStrategy` 中脆弱的 Hack，并为未来的持久化调度和远程执行节点奠定了协议基础。同时，通过统一“哈希强制长命名规范”，我们大幅提升了系统底层的可读性与健壮性。

### 目标
创建一个完整的 Git 提交，包含以下核心变更：
1.  **协议定义**: 在 `cascade-spec` 中引入 `Assembly` 和 `SymbolTable`。
2.  **编译器升级**: `Builder` 现在产出 `Assembly`，并自动填充符号表映射。
3.  **哈希规范化**: 全局统一使用 `canonical_code_structure_hash`。
4.  **运行时重构**: 实现 `CodeRegistry` 和 `Linker`，重写 `VMExecutionStrategy`。
5.  **质量保证**: 包含 Assembly 纯粹性测试和 VM 策略的端到端集成测试。

### 基本原理
我们通过在物理图之外引入一个显式的“符号表 (Symbol Table)”，将静态的拓扑结构与动态的可执行代码解耦。这允许图在不同进程、不同机器甚至不同时间被加载和链接，只要目标环境的 `CodeRegistry` 能够提供符合规范哈希的函数实现。

### 标签
#intent/build #flow/ready #priority/high #comp/spec #comp/compiler #comp/vm #comp/engine #concept/linker #scope/api #ai/instruct #task/domain/compiler #task/object/linker-protocol #task/action/implementation #task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交链接协议的完整实现

我们将所有受影响的包、新创建的模块以及修复后的测试用例添加到暂存区。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/assembly.py
packages/cascade-spec/src/cascade/spec/__init__.py
packages/cascade-spec/src/cascade/spec/ir/models.py
packages/cascade-reflection/src/cascade/reflection/analyzer.py
packages/cascade-reflection/src/cascade/reflection/hashing.py
packages/cascade-reflection/src/cascade/reflection/naming.py
packages/cascade-compiler/src/cascade/compiler/backend/builder.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/tests/integration/test_assembly_purity.py
packages/cascade-compiler/tests/unit/backend/test_builder.py
packages/cascade-compiler/tests/unit/backend/test_builder_environment.py
packages/cascade-compiler/tests/unit/backend/test_builder_observability.py
packages/cascade-compiler/tests/unit/backend/test_expander.py
packages/cascade-compiler/tests/unit/frontend/test_generator.py
packages/cascade-compiler/tests/integration/test_graph_purity.py
packages/cascade-compiler/tests/integration/test_resource_contention.py
packages/cascade-compiler/tests/integration/test_sovereign_wiring.py
packages/cascade-vm/src/cascade/vm/registry.py
packages/cascade-vm/src/cascade/vm/linker.py
packages/cascade-vm/tests/integration/test_resource_backpressure.py
packages/cascade-vm/tests/integration/test_source_node_execution.py
packages/cascade-engine/src/cascade/runtime/strategies/vm.py
packages/cascade-engine/tests/integration/test_vm_strategy.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-graph/src/cascade/graph/hashing.stitcher.yaml
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat: Implement Cascade 3.0 Assembly and the Linker Protocol

This commit introduces a standard compilation and linking model, decoupling
graph topology from runtime executable code.

Key Highlights:
1. Spec: Added 'Assembly' and 'SymbolTable' models to 'cascade-spec'.
2. Compiler: Upgraded 'Builder' to produce 'Assembly' objects. Worker nodes are
   now automatically mapped to their canonical code hashes in the symbol table.
3. Hashing: Unified all code-structure-related hashes to 'canonical_code_structure_hash'
   across 'reflection', 'compiler', and 'graph' packages.
4. Runtime:
   - Implemented 'CodeRegistry' for managing 'Hash -> Callable' mappings.
   - Implemented 'Linker' to bind 'Assembly' to 'CodeRegistry' at load time.
   - Refactored 'VMExecutionStrategy' to use the new protocol, removing legacy hacks.
5. Verification:
   - Added 'test_assembly_purity' to ensure compiled assets remain serializable.
   - Added 'test_vm_strategy_e2e' for full pipeline validation.

This architecture enables true distributed execution and persistent task scheduling
by providing a stable, verifiable identity for all computational units.
~~~~~

### 下一步建议

"The Linker Protocol" 的成功实施为我们打开了多扇大门。接下来的方向建议：
1.  **分布式执行雏形**: 既然 `Assembly` 是纯粹可序列化的，我们可以尝试编写一个简单的脚本，将编译好的 `Assembly` 通过网络发送给另一个进程中的 `Linker` 执行。
2.  **JIT 优化器启动**: 现在的物理图是完全保真但冗余的。我们可以开始在 `Linker` 之前或作为其一部分，引入 JIT 优化（如路线图提到的常量折叠和算子融合）。
3.  **持久化缓存**: 利用 `canonical_code_structure_hash` 实现基于代码内容感知的持久化结果缓存。

再次祝贺完成这一核心重构！
