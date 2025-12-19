好的，我们来创建一个描述这一架构级修复的 Git 提交。

这个提交将包含对 `cs-controller` 客户端和 `cascade-runtime` 核心管理器的修改，确保了控制平面操作的幂等性和状态的互斥性。

## [COMMIT] fix(control-plane): Implement idempotent and exclusive constraint management

### 用户需求
解决当用户多次发布相同作用域和类型的约束（例如，两次设置 `global` 作用域的速率限制）时，`Engine` 陷入不确定状态或死锁的问题。

### 评论
此修复是控制平面健壮性的核心。通过引入“最后写入为准 (Last-Write-Wins)”的语义，我们解决了由客户端生成随机 ID（导致累积冲突约束）和服务器端缺乏冲突解决机制所导致的深层缺陷。

**关键更改:**
1.  **`cs-controller`**: 客户端现在为 `pause`、`concurrency` 和 `rate_limit` 约束生成**确定性 ID**（格式为 `f"{type}-{scope}"`）。这使得用户的重复命令被视为**更新**而不是**新增**。
2.  **`ConstraintManager`**: 在 `update_constraint` 中添加了防御性逻辑，它会主动搜索并移除任何具有相同 `(scope, type)` 但 ID 不同的旧约束。这保证了对于任何给定的控制意图，系统中只存在一个活跃的约束，从而消除了不确定行为和死锁的可能。

### 目标
创建一个单一的、逻辑完整的提交，封装幂等性约束管理机制的实现。

### 基本原理
控制平面操作必须是幂等的。强制使用确定性 ID，并实现服务器端互斥性检查，确保了 Cascade 能够从不一致的状态中恢复，并提供可靠的动态控制能力。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/control-plane #task/object/constraint-management #task/action/implement-idempotency #task/state/end

---

### Script

#### Acts 1: 提交变更

将修改后的文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
tests/py/e2e/test_e2e_runtime_control_updates.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
fix(control-plane): Implement idempotent and exclusive constraint management

This commit resolves a critical design flaw where multiple constraints of the same (scope, type) could accumulate, leading to undefined behavior and deadlocks, particularly with rate limits.

Key architectural changes:
1.  **Idempotent CLI (Client-side):** The `cs-controller` no longer generates random UUIDs for constraints (pause, limit). It now uses a deterministic ID based on the constraint type and scope (e.g., "rate_limit-global"). This ensures that repeat commands correctly UPDATE the constraint via MQTT's retained message feature.
2.  **Exclusive Constraints (Server-side):** `ConstraintManager.update_constraint` now includes logic to explicitly search for and remove any existing constraints that share the same (scope, type) but have a different ID before accepting the new constraint.

This enforces a strict "Last-Write-Wins" policy, guaranteeing that only one effective constraint exists for any given control intent, thereby eliminating resource conflict deadlocks in the Engine's scheduling loop.
~~~~~

### 下一步建议
我们已经完成了对并发安全和控制平面架构的重大改进。根据我们在 **展望与路线/重构路线图：实现 Cascade 的并发安全.md** 中定义的路线图，所有步骤均已标记为 `#DONE`。

现在，我们可以考虑解决你在 `开发/状态检测/债务监测.md` 中提出的另一个架构债务：

> **技术债务分析：`cs.template` 的 API 人体工程学**
> `cs.template` 的原始设计允许使用 `**kwargs` 来传递模板上下文，但这对于 `LazyResult` 类型的动态值会立即失败。当前解决方案是要求用户使用显式的 `context=lazy_context` 字典。
> **潜在的未来改进**: 引入一个新的原子提供者，例如 `cs.dict` 或 `cs.merge`，允许用户在图内部动态地创建和合并字典。

我建议现在着手实现 `cs.dict` (我们将其命名为 `cs.merge` 更合适，因为它侧重于合并上下文)，以增强 `Cascade` 的组合能力。

如果你同意，我将生成实现 `cs.merge` 提供者的计划。
