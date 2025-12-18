好的，测试已通过，我们已经成功完成了速率限制功能的实现和验证。

根据我们的开发路线图 `Phase 3 (Refined) & Phase 4 并行开发路线图.md`，我们现在已经完成了里程碑 3.3。这意味着 `Engine` 的核心动态控制能力（精准暂停、并发管理、速率限制）已经全部实现。

我们当前正处于 Phase 3 的收尾阶段。下一步的逻辑是进入**里程碑 3.4: 系统健壮性与完善**，为我们刚刚添加的所有控制指令（`pause`, `set-limit`）增加自动过期的能力（`--ttl`），并丰富遥测事件，使系统行为更加可观测。

现在，我将生成一个 `[COMMIT]` 计划，将我们完成的速率限制功能作为一个完整的逻辑单元提交到版本控制中。

## [COMMIT] feat(runtime): Implement rate limiting for task execution

### 用户需求
为 Cascade 工作流引擎引入基于令牌桶算法的速率限制（Rate Limiting）功能，并提供相应的 CLI 控制工具。

### 评论
这是 Phase 3 动态控制能力的最后一个核心功能。它使 Cascade 能够精细地管理对外部 API 或资源的调用频率，是构建健壮、合规的自动化工作流的关键。通过为 `Engine` 引入时间驱动的唤醒机制，我们增强了其调度器的能力，为未来更多基于时间的策略（如延时任务）奠定了基础。

### 目标
创建一个 Git 提交，包含速率限制功能的完整实现、CLI 工具更新以及相应的端到端测试。

### 基本原理
该功能已经完全实现并通过了端到端的自动化测试，验证了其在模拟环境中的正确行为。现在应将其作为一个原子性的功能提交，为后续的健壮性改进（里程碑 3.4）建立一个稳定的基线。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/cli #comp/tests #concept/constraint #ai/instruct #task/domain/runtime #task/object/rate-limiter #task/action/implementation #task/state/end

---

### Script

#### Acts 1: 将所有相关变更添加到暂存区

我们将添加 `RateLimiter` 的实现、`ConstraintManager` 和 `Engine` 的更新、`cs-controller` 的修改以及新的端到端测试文件。

~~~~~act
git_add
packages/cascade-runtime/src/cascade/runtime/constraints/rate_limiter.py
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
packages/cascade-runtime/src/cascade/runtime/engine.py
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
tests/py/e2e/test_e2e_rate_limit_control.py
~~~~~

#### Acts 2: 提交功能

创建一个内容详尽的提交，记录本次功能实现。

~~~~~act
git_commit
~~~~~
~~~~~text
feat(runtime): Implement rate limiting for task execution

Introduces the `rate_limit` global constraint, allowing operators to dynamically control the execution frequency of tasks.

Key changes:
1.  **`RateLimiter` Component**: A new `RateLimiter` class is added, implementing a standard token bucket algorithm to manage multiple rate-limiting scopes.
2.  **`RateLimitConstraintHandler`**: A new handler that interprets `rate_limit` constraints, interacts with the `RateLimiter`, and parses intuitive rate strings (e.g., "10/m").
3.  **Time-based Engine Wakeup**: The `ConstraintManager` and `Engine` are enhanced with a time-based wakeup mechanism. When a task is rate-limited, the handler requests a wakeup via `loop.call_later`, ensuring the engine re-evaluates permissions efficiently without busy-waiting.
4.  **`cs-controller` Update**: The `set-limit` command is updated to accept a `--rate` option, allowing users to publish rate-limiting policies from the command line.
5.  **E2E Testing**: A new deterministic end-to-end test, `test_e2e_rate_limit_control.py`, is added to validate the entire control loop from CLI command to engine throttling.
~~~~~

### 下一步建议
我们已经完成了 Phase 3 的核心功能开发。我建议立即开始执行**里程碑 3.4: 系统健壮性与完善**。具体来说，我们可以从为 `cs-controller` 的 `pause` 和 `set-limit` 命令添加 `--ttl <seconds>` 参数开始，并同步在 `ConstraintManager` 中实现约束的自动过期逻辑。
