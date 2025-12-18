TTL 功能的实现已经完成，代码和 E2E 测试均已就绪。现在生成提交计划。

我们将把所有修改和新增文件（包括 E2E 测试）添加到 Git 暂存区，并创建一个描述性的提交。

## [COMMIT] feat(runtime,cli): Add TTL support for global constraints and automatic cleanup

### 用户需求
用户希望发布的控制指令（如“暂停”或“限流”）能够只持续一段时间（例如“暂停 5 分钟”），之后自动失效，而不需要人工介入去手动恢复。

### 评论
此功能是实现健壮的自适应控制架构的关键一环。它极大地增强了系统的自动化运维能力，允许用户设置临时策略而无需人工恢复，降低了操作风险。新的 E2E 测试验证了约束的自动清理和任务的恢复。

### 目标
创建一个完整的 Git 提交，将约束 TTL 的核心实现和 `cs-controller` 的参数更新包含在内。

### 基本原理
我们利用 `ConstraintManager` 的调度唤醒机制，将约束的 `expires_at` 转换为定时的 `asyncio.call_later` 唤醒事件。`Engine` 在被唤醒后，会通过 `ConstraintManager.cleanup_expired_constraints()` 清理过期的约束。`_remove_constraint_by_id` 确保了在约束过期时，相应的 Handler（例如 `ConcurrencyConstraintHandler`）的清理逻辑能够被触发，从而正确释放资源并恢复被阻塞的任务。

### 标签
#intent/build #flow/done #priority/medium 
#comp/runtime #comp/cli #concept/config #scope/core #scope/dx 
#ai/instruct 
#task/domain/ops #task/object/constraint-ttl #task/action/implement 
#task/state/end

---

### Script

#### Acts 1: 暂存并提交所有 TTL 相关的变更

将运行时逻辑、CLI 工具更新以及新的 E2E 测试文件添加到暂存区，并执行提交。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
tests/py/e2e/test_e2e_ttl.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime,cli): Add TTL support for global constraints and automatic cleanup

Implements Time-To-Live (TTL) functionality for all global constraints, enabling temporary policies (like pause or limit) that automatically expire.

Key Changes:
1.  **ConstraintManager**: Added `expires_at` handling in `update_constraint` to schedule a future wakeup event in the Engine. Implemented `cleanup_expired_constraints` to sweep and remove expired constraints, triggering necessary `on_constraint_remove` handler logic.
2.  **Engine**: Updated the main execution loop to call `cleanup_expired_constraints` after every `_wakeup_event.wait()` completes, ensuring prompt cleanup after TTL expires.
3.  **cs-controller**: Added the `--ttl <seconds>` option to both `pause` and `set-limit` commands, calculating the absolute `expires_at` timestamp before publishing the retained MQTT message.

This feature ensures that temporary control policies do not permanently block workflows, significantly improving system robustness and ease of operation.
~~~~~

### 下一步建议
我们已经完成了 Phase 3 的所有核心功能（精准控制、并发/速率限制、TTL）。

根据路线图，下一个逻辑步骤是开始 **Phase 5：躯体与记忆 (The Soma & Memory Layer)** 的第一个里程碑：

- **里程碑 5.1**: 实现 **`RedisStateBackend`** 和 **`RedisCacheBackend`**。这将允许 Cascade 实例之间共享任务结果，实现持久化和跨进程协作。

我建议下一个计划着手进行 Redis 后端的实现。
