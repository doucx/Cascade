这是一个非常奇怪的现象。如果 `Mock calls` 是空的，且没有看到 `DEBUG: Caught exception...`，这强烈暗示**异常处理逻辑根本没有被触发**。这通常意味着消息没有被正确路由到 `Engine`，或者在到达 Handler 之前就被丢弃了。

为了彻底查清消息是在哪里“消失”的，我们需要追踪消息在 `Engine` 内部的完整流转路径。

## [WIP] chore(debug): 增强调试探针以追踪消息流转

### 用户需求
在 `Engine` 的消息接收入口和 `ConstraintManager` 的分发逻辑中添加调试日志，以确定消息丢失的位置。

### 评论
目前的调试信息不足以定位问题。我们需要知道：
1.  `Engine` 是否从 `Connector` 收到了 MQTT 消息？
2.  如果收到了，`ConstraintManager` 是否正确识别了它？
3.  `ConstraintManager` 是否找到了对应的 `RateLimitConstraintHandler`？

### 目标
1.  修改 `cascade-engine/src/cascade/runtime/engine.py`，在 `_on_constraint_update` 中添加日志。
2.  修改 `cascade-engine/src/cascade/runtime/constraints/handlers.py`，在 `on_constraint_add` 入口处添加日志。

### 基本原理
通过在数据流的关键节点（入口、路由、处理）打点，我们可以利用“排除法”快速锁定问题区域。

### 标签
#intent/tooling #flow/ready #priority/high #comp/debug #scope/core #ai/instruct #task/domain/debugging #task/action/instrument #task/state/continue

---

### Script

#### Acts 1: 在 `Engine` 消息入口添加日志

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/engine.py
~~~~~
~~~~~python
    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
        """Callback to handle incoming constraint messages."""
        try:
            # An empty payload, which becomes {}, signifies a cleared retained message (a resume command)
            if payload == {}:
~~~~~
~~~~~python
    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
        """Callback to handle incoming constraint messages."""
        print(f"DEBUG: Engine received update on topic '{topic}': {payload}")
        try:
            # An empty payload, which becomes {}, signifies a cleared retained message (a resume command)
            if payload == {}:
~~~~~

#### Acts 2: 在 `RateLimitConstraintHandler` 入口添加日志

~~~~~act
patch_file
packages/cascade-engine/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        rate_val = constraint.params.get("rate", "1/s")
        rate_hertz = _parse_rate_string(str(rate_val))

        # We can optionally allow users to set burst capacity via params
~~~~~
~~~~~python
    def on_constraint_add(
        self, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> None:
        print(f"DEBUG: RateLimitHandler received constraint: {constraint}")
        rate_val = constraint.params.get("rate", "1/s")
        rate_hertz = _parse_rate_string(str(rate_val))

        # We can optionally allow users to set burst capacity via params
~~~~~

### 下一步建议

请再次运行测试。

*   如果看不到 `DEBUG: Engine received update...`，说明 `Connector` 没有把消息推给 `Engine`（订阅路径问题）。
*   如果看到了 `Engine received...` 但没看到 `RateLimitHandler received...`，说明 `ConstraintManager` 没调用 Handler（注册问题或类型匹配问题）。
*   如果都看到了，但还是没异常日志，那就是玄学了（需要检查 `_parse_rate_string` 是否被 Mock 了？但这不可能）。

根据输出，我们将知道下一步该修哪里。
