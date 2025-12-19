我们将一次性完成对 `cascade-cli-controller` 和 `cascade-runtime` 的重构，实现“最后写入为准 (Last-Write-Wins)”的约束管理策略，并引入确定性的约束 ID。

这将直接修复之前在 `test_e2e_runtime_control_updates.py` 中由于多重约束冲突导致的不确定行为，使系统行为变得健壮且可预测。

## [WIP] fix(core): 实现幂等的约束更新机制

### 用户需求
1.  修改 `cs-controller`，在生成约束时使用基于 `type` 和 `scope` 的确定性 ID，而非随机 UUID。这确保了多次执行相同的命令会被视为对同一约束的更新。
2.  修改 `cascade-runtime` 中的 `ConstraintManager`，引入显式的冲突解决逻辑：当添加一个新约束时，自动清除所有与之具有相同 `(scope, type)` 但 ID 不同（如果存在）的旧约束，以此作为双重保险。

### 评论
这是一个架构级的修复，它确立了 Cascade 控制平面“单一事实来源”和“最后写入为准”的原则。通过在 CLI 端保证 ID 的稳定性，以及在 Engine 端保证作用域的互斥性，我们消除了产生冲突规则的可能性，从根本上解决了死锁和状态不一致的问题。

### 目标
1.  **CLI 重构**: 修改 `packages/cascade-cli-controller/src/cascade/cli/controller/app.py`，移除 `uuid.uuid4()`，改用确定性字符串作为 ID。
2.  **Runtime 重构**: 修改 `packages/cascade-runtime/src/cascade/runtime/constraints/manager.py`，在 `update_constraint` 方法中添加逻辑，先移除所有同作用域同类型的旧约束。
3.  **提交**: 生成一个 Git 提交。

### 基本原理
-   **CLI 端**: 使用 `f"{type}-{scope}"` 作为 ID，不仅实现了幂等性，还让 MQTT 消息本身变得更加语义化和易读。
-   **Runtime 端**: 即使客户端表现良好，防御性编程也是必要的。`ConstraintManager` 应作为最终的看门人，确保任何时候对于一个给定的 `(scope, type)` 组合，只存在一个活跃的约束对象。

### 标签
#intent/fix #flow/ready #priority/high #comp/cli #comp/runtime #concept/state #scope/core #ai/instruct #task/domain/control-plane #task/object/constraint-management #task/action/implement-idempotency #task/state/end

---

### Script

#### Acts 1: 重构 `cs-controller` 以使用确定性 ID

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
        # Create a unique, descriptive ID for the constraint
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        expires_at = time.time() + ttl if ttl else None

        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
        )
~~~~~
~~~~~python
        # Create a deterministic ID for idempotency (Last-Write-Wins)
        constraint_id = f"pause-{scope}"
        expires_at = time.time() + ttl if ttl else None

        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="pause",
            params={},
            expires_at=expires_at,
        )
~~~~~

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        expires_at = time.time() + ttl if ttl else None

        if concurrency is not None:
            constraint_id = f"concurrency-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
                expires_at=expires_at,
            )
            bus.info(
                "controller.publishing_limit",
                scope=scope,
                topic=topic,
                limit=concurrency,
            )
            await connector.publish(topic, asdict(constraint), retain=True)

        if rate is not None:
            constraint_id = f"ratelimit-{scope}-{uuid.uuid4().hex[:8]}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
                expires_at=expires_at,
            )
            bus.info("controller.publishing_rate", scope=scope, topic=topic, rate=rate)
            await connector.publish(topic, asdict(constraint), retain=True)
~~~~~
~~~~~python
        topic = f"cascade/constraints/{scope.replace(':', '/')}"
        expires_at = time.time() + ttl if ttl else None

        if concurrency is not None:
            constraint_id = f"concurrency-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="concurrency",
                params={"limit": concurrency},
                expires_at=expires_at,
            )
            bus.info(
                "controller.publishing_limit",
                scope=scope,
                topic=topic,
                limit=concurrency,
            )
            await connector.publish(topic, asdict(constraint), retain=True)

        if rate is not None:
            constraint_id = f"ratelimit-{scope}"
            constraint = GlobalConstraint(
                id=constraint_id,
                scope=scope,
                type="rate_limit",
                params={"rate": rate},
                expires_at=expires_at,
            )
            bus.info("controller.publishing_rate", scope=scope, topic=topic, rate=rate)
            await connector.publish(topic, asdict(constraint), retain=True)
~~~~~

#### Acts 2: 重构 `ConstraintManager` 以实现互斥更新

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

        # Schedule wakeup if TTL is set
        if constraint.expires_at:
            now = time.time()
            if constraint.expires_at > now:
                self.request_wakeup(constraint.expires_at - now)

        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_add(constraint, self)
~~~~~
~~~~~python
    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """
        Adds a new constraint or updates an existing one.
        Ensures strict 'Last-Write-Wins' behavior by removing any existing
        constraints with the same (scope, type) but different ID.
        """
        # 1. Clean up conflicts: Remove any existing constraint with same scope & type
        conflicting_ids = [
            cid
            for cid, c in self._constraints.items()
            if c.scope == constraint.scope
            and c.type == constraint.type
            and cid != constraint.id
        ]
        for cid in conflicting_ids:
            self._remove_constraint_by_id(cid)

        # 2. Add/Update the new constraint
        self._constraints[constraint.id] = constraint

        # Schedule wakeup if TTL is set
        if constraint.expires_at:
            now = time.time()
            if constraint.expires_at > now:
                self.request_wakeup(constraint.expires_at - now)

        handler = self._handlers.get(constraint.type)
        if handler:
            handler.on_constraint_add(constraint, self)
~~~~~

### 下一步建议
恭喜！我们已经完成了并发安全重构路线图中的关键部分，并解决了一个严重的架构缺陷。系统现在应该更加健壮了。

我建议运行一次完整的测试套件（`pytest tests/`），以确保我们的更改没有引入任何回归问题。如果一切顺利，我们就可以认为这一阶段的重构圆满结束了。

