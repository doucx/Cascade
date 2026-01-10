好的，我们已经完成了第一阶段的架构重构工作。现在，我们将这些改动作为一个完整的逻辑单元提交到版本库中。

## [COMMIT] refactor: 提升导出层级、隔离测试支架并迁移核心协议至 spec

### 用户需求
将之前进行的 `__init__.py` 导出优化、`EventDrivenRunner` 迁移以及核心协议（`ReactorProtocol`, `ExpansionPolicy` 等）向 `spec` 包的迁移进行提交。

### 评论
这次提交标志着项目向 **HFEA v1.0** 定义的“本体论正确性”迈出了重要一步。通过物理隔离测试逻辑和提升契约定义的地位，我们显著降低了系统的模块间耦合度，并为后续的跨语言实现（如 Rust 版 Reactor）打下了基础。

### 目标
1.  提交 `cascade-compiler` 和 `cascade-runtime` 的导出优化。
2.  提交 `EventDrivenRunner` 从 `cascade-vm` 到 `cascade-test-utils` 的物理迁移及相关的测试路径修复。
3.  提交核心协议（VM 接口、编译器策略和 SubGraph 模型）向 `cascade-spec` 的迁移。

### 基本原理
按照 Quipu 协议，在完成一系列文件变更后，应当通过一个专门的 `[COMMIT]` 计划来固化这些成果。这确保了 Git 历史的清晰，并使每个提交都对应一个具有明确架构意义的步骤。

### 标签
#intent/refine #flow/ready #priority/medium 
#comp/compiler #comp/runtime #comp/vm #comp/spec #comp/tests
#task/domain/architecture #task/object/monorepo-structure #task/action/commit
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 提交架构重构变更

我们将所有修改过的文件添加到暂存区，并创建一个描述详尽的提交。

~~~~~act
git_add
packages/cascade-compiler/src/cascade/compiler/__init__.py
packages/cascade-compiler/src/cascade/compiler/backend/expander.py
packages/cascade-compiler/src/cascade/compiler/backend/expansion/protocol.py
packages/cascade-compiler/src/cascade/compiler/backend/wiring/protocol.py
packages/cascade-runtime/src/cascade/runtime/__init__.py
packages/cascade-test-utils/src/cascade/test_utils/harness.py
packages/cascade-test-utils/src/cascade/test_utils/__init__.py
packages/cascade-vm/src/cascade/vm/harness.py
packages/cascade-vm/src/cascade/vm/protocols.py
packages/cascade-vm/tests/integration/test_context_injection.py
packages/cascade-vm/tests/integration/test_linker_validation.py
packages/cascade-vm/tests/integration/test_ref_architecture.py
packages/cascade-vm/tests/integration/test_resource_contention.py
packages/cascade-vm/tests/integration/test_resource_sentry.py
packages/cascade-vm/tests/integration/test_retry_topology.py
packages/cascade-vm/tests/integration/test_source_node_execution.py
packages/cascade-vm/tests/unit/test_reactor.py
packages/cascade-spec/src/cascade/spec/compiler/model.py
packages/cascade-spec/src/cascade/spec/compiler/interfaces.py
packages/cascade-spec/src/cascade/spec/vm/interfaces.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor: improve architecture by elevating exports, isolating test utilities, and migrating core protocols to spec

- Elevated key compiler and runtime components (Builder, IRGenerator, TelemetrySubscriber, Events) to package roots for better DX.
- Moved `EventDrivenRunner` from `cascade-vm` to `cascade-test-utils` to separate test infrastructure from production code.
- Migrated `SubGraph` model and `ExpansionPolicy`, `WiringPolicy`, `ReactorProtocol` to `cascade-spec` to decouple definitions from implementations.
- Updated all internal references and imports across the monorepo to align with the new package structure.
- Fixed import paths in VM integration and unit tests.
~~~~~

### 下一步建议
- **运行测试**: 执行 `pytest packages/cascade-vm/tests` 确保重构后的测试套件依然能够通过。
- **处理硬编码**: 针对审计报告中的第 4 项，着手处理 `Machine.run` 中的硬编码 `sleep(0.001)`，引入更稳健的自适应等待机制。
- **内置任务迁移**: 考虑将 `reflection.tasks` 中的内置任务（如 `_internal_gather`）移动到 `cascade-std` 中。
