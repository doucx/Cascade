生成 Quipu 计划。

好的，既然测试已经通过，我将生成一个 `[COMMIT]` 计划。该计划将把所有类型修复和 Provider 架构重构的变更提交到 Git 仓库，从而标志着这一阶段质量改进工作的完成。

## [COMMIT] fix(type): 修复全仓库类型错误并重构 Provider 协议架构

### 错误分析
本次提交修复了全仓库约 105 个 Pyright 识别出的类型错误。
1.  **协议不兼容**: `Provider` 和 `Connector` 协议定义过于严格，导致实现类报错。
2.  **空值安全**: 修复了大量 `Optional` 类型在使用前未进行 `None` 检查的隐患。
3.  **循环引用与位置错误**: `Provider` 协议原本位于 `cascade-sdk`，导致底层库依赖不合理。
4.  **接口缺失**: 补充了 `StateBackend` 等核心协议中缺失的 `clear` 方法。

### 用户需求
完成类型修复和架构重构的原子化提交。

### 评论
这是一次深度的“技术债”清理。通过修复这些静态检查错误，我们不仅提高了代码的健壮性（避免了潜在的运行时 `NoneType` 错误），还通过将协议下沉至 `cascade-spec` 进一步理顺了依赖树。解耦 `ProviderRegistry` 实施则为未来的单元测试提供了更好的隔离性。

### 目标
1.  将所有修改过的文件添加到 Git 暂存区。
2.  创建一个包含详细说明的 Git Commit。

### 基本原理
遵循 `COMMIT` 计划规范，本计划仅包含 Git 操作。所有文件系统变更已在之前的 `WIP` 步骤中完成并验证。

### 标签
#intent/fix #intent/refine #flow/done #priority/medium #comp/spec #comp/sdk #comp/engine #comp/library #ai/instruct #task/domain/testing #task/object/type-hints #task/action/fix #task/state/end

---

### Script

#### Acts 1: 提交变更

我们将暂存所有受影响的包，并提交这些改进。

~~~~~act
git_add
packages/cascade-spec/src/cascade/spec/protocols.py
packages/cascade-spec/src/cascade/spec/resource.py
packages/cascade-spec/src/cascade/spec/routing.py
packages/cascade-sdk/src/cascade/providers/registry.py
packages/cascade-sdk/src/cascade/providers/manager.py
packages/cascade-connector-local/src/cascade/connectors/local/connector.py
packages/cascade-connector-local/src/cascade/connectors/local/bus.py
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
packages/cascade-engine/src/cascade/adapters/cache/redis.py
packages/cascade-engine/src/cascade/adapters/state/redis.py
packages/cascade-engine/src/cascade/adapters/solvers/csp.py
packages/cascade-engine/src/cascade/runtime/constraints/rate_limiter.py
packages/cascade-engine/src/cascade/runtime/constraints/handlers.py
packages/cascade-engine/src/cascade/runtime/engine.py
packages/cascade-engine/src/cascade/runtime/processor.py
packages/cascade-engine/src/cascade/runtime/resolvers.py
packages/cascade-engine/src/cascade/runtime/flow.py
packages/cascade-engine/src/cascade/runtime/strategies/graph.py
packages/cascade-engine/src/cascade/runtime/vm.py
packages/cascade-engine/src/cascade/runtime/resource_container.py
packages/cascade-library/src/cascade/providers/config.py
packages/cascade-library/src/cascade/providers/sql.py
packages/cascade-graph/src/cascade/graph/compiler.py
packages/cascade-graph/src/cascade/graph/serialize.py
packages/cascade-sdk/src/cascade/testing.py
packages/cascade-sdk/src/cascade/tools/cli.py
packages/cascade-provider-ipfs/src/cascade/providers/ipfs/provider.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(type): resolve 105+ Pyright errors and refactor Provider architecture

Core improvements:
- Move 'Provider' and 'LazyFactory' protocols to 'cascade-spec' to unify the dependency base.
- Decouple 'ProviderRegistry' implementation from its singleton instance in 'cascade-sdk' for better testability.
- Fix 'StateBackend' protocol by adding missing 'clear()' method.
- Resolve dozens of "possibly None" type errors in Engine and Connectors using strict null checks.
- Align Protocol definitions (e.g., name: str instead of @property) with implementation realities.
- Fix signature inspection issues in 'ResourceContainer' and 'CLI' tools.
- Update SQL and IPFS providers to support **kwargs for LazyFactory compatibility.

This commit significantly improves static type safety and clears the dependency path between Library, SDK, and Spec.
~~~~~

### 下一步建议
类型系统现在是健康的。建议：
1.  **CI 集成**: 在 CI 工作流中加入 `pyright` 检查，确保未来不会引入新的类型回归。
2.  **文档更新**: 既然 `Provider` 协议已经移动，可以更新 `docs/reference/api.md` 中关于扩展系统的说明。
