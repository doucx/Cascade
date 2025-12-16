好的，我将根据前一个计划中的修改内容，创建一个 `[COMMIT]` 计划，用于提交所有文件系统和代码的变更。

## [COMMIT] refactor(messaging): Centralize message formatting and remove MessageStore hack

### 用户需求
对上一个 `[WIP]` 计划中完成的文件修改进行提交操作。
2. 创建 `src/cascade/locales/en/events.json` 消息模板文件。
3. 移除 `src/cascade/messaging/bus.py` 中用于消息格式化的临时逻辑。
4. 更新 `tests/integration/test_end_to_end.py`，断言正确的语义数据结构。

### 评论
这个提交解决了消息传递层中的一个关键不一致性，将消息格式化的逻辑从运行时核心（`MessageStore`）转移到了声明式的本地化资源文件（`events.json`）。这遵循了我们“验证意图而非实现”的测试原则，提高了代码的模块化和健壮性。

### 目标
执行 `git_add` 和 `git_commit`，将本次重构作为一个完整的逻辑单元提交。

### 基本原理
文件系统修改和 Git 提交必须隔离到独立的计划中。本次计划将所有文件变更和元数据移动操作进行原子提交。

### 标签
#intent/refine #flow/ready #priority/medium
#comp/runtime #comp/tests #concept/state #scope/dx
#ai/instruct
#task/domain/maintenance #task/object/tech-debt #task/action/commit #task/state/end

---

### Script

#### Acts 1: 提交文件变更

将所有修改和新增的文件添加到 Git 暂存区，并执行提交。

~~~~~act
git_add
src/cascade/locales/en/events.json
src/cascade/messaging/bus.py
tests/integration/test_end_to_end.py
~~~~~

~~~~~act
git_commit
~~~~~
~~~~~text
refactor(messaging): Centralize message formatting and remove MessageStore hack

This commit refactors the message passing and rendering mechanism to adhere strictly to the principle of "asserting intent over implementation" and to eliminate unnecessary internal complexity.

Key changes:
1.  **Introduce `events.json`:** The file `src/cascade/locales/en/events.json` is created to serve as the Single Source of Truth for all human-readable message templates.
2.  **Remove `MessageStore` hack:** The temporary logic in `MessageStore.get` that manually joined the `target_tasks` list into a string is removed. The store now simply passes the raw event data to the template formatter.
3.  **Refine Test Intent:** Updated `tests/integration/test_end_to_end.py` to correctly assert that the `HumanReadableLogSubscriber` passes the list structure (e.g., `target_tasks=["greet"]`) directly to the messaging bus, rather than the previous, manually joined string.

~~~~~
