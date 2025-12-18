好的，我们继续推进。

我们已经为 `Engine` 植入了一个能够感知约束的调度循环。现在，是时候为它装上“耳朵”了——通过 `Connector` 协议，让 `Engine` 能够实时接收来自外部世界的指令，并动态更新其内部的约束状态。

这将完成我们反馈回路的输入部分，是实现运行时控制的关键。

## [WIP] feat: 实现通过 Connector 的约束动态同步

### 用户需求
实现 `Engine` 通过 `Connector` 协议订阅并处理外部约束更新的功能。

### 评论
这是将 Cascade 从一个封闭系统转变为一个开放、可控系统的决定性一步。通过建立这个订阅机制，我们为 `Engine` 打开了一个接收实时指令的通道。这意味着系统的行为不再仅仅由预先定义的代码决定，而是可以被运行环境动态地塑造和引导，这对于实现 A/B 测试、功能开关、紧急熔断等高级运维模式至关重要。

### 目标
1.  修改 `Engine.run()` 方法，在与 `Connector` 建立连接后，立即订阅一个用于接收约束指令的预定主题（例如 `cascade/constraints/#`）。
2.  在 `Engine` 类中实现一个新的私有回调方法 `_on_constraint_update`。
3.  该回调方法将负责解析收到的消息（假定为 JSON），将其构造成一个 `GlobalConstraint` 对象。
4.  最后，调用 `self.constraint_manager.update_constraint()`，将新的或更新的约束应用到 `Engine` 的本地状态中。

### 基本原理
我们通过在 `Engine` 的生命周期早期（`run` 方法开始时）建立订阅，来确保工作流在整个执行期间都能接收到指令。使用一个专用的回调方法 `_on_constraint_update`，可以将消息处理逻辑与 `Engine` 的核心调度逻辑解耦，保持代码的清晰和可维护性。这种设计完全遵循了我们预先定义的 `Connector` 协议，使得 `Engine` 的核心代码与具体的通信技术（如 MQTT）无关。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/interfaces #concept/constraints #concept/sync #scope/core
#ai/instruct
#task/domain/runtime #task/object/constraint-system #task/action/integration #task/state/continue

---

### Script

#### Acts 1: 添加必要的 import

首先，我们需要在 `engine.py` 中导入 `GlobalConstraint`，以便在回调函数中使用它。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.runtime.bus import MessageBus
~~~~~
~~~~~python
from cascade.spec.resource import ResourceDefinition, Inject
from cascade.spec.constraint import GlobalConstraint
from cascade.runtime.bus import MessageBus
~~~~~

#### Acts 2: 实现订阅逻辑和回调方法

现在，我们将修改 `Engine.run` 方法来发起订阅，并添加处理消息的回调方法 `_on_constraint_update`。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        try:
            if self.connector:
                await self.connector.connect()

            with ExitStack() as stack:
                initial_graph = build_graph(target)
                required_resources = self._scan_for_resources(initial_graph)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id, state_backend
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
            raise
        finally:
            if self.connector:
                await self.connector.disconnect()
~~~~~
~~~~~python
        try:
            if self.connector:
                await self.connector.connect()
                # Subscribe to constraint updates
                await self.connector.subscribe(
                    "cascade/constraints/#", self._on_constraint_update
                )

            with ExitStack() as stack:
                initial_graph = build_graph(target)
                required_resources = self._scan_for_resources(initial_graph)
                active_resources = self._setup_resources(
                    required_resources, stack, run_id
                )

                final_result = await self._execute_graph(
                    target, params or {}, active_resources, run_id, state_backend
                )

            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(run_id=run_id, status="Succeeded", duration=duration)
            )
            return final_result

        except Exception as e:
            duration = time.time() - start_time
            self.bus.publish(
                RunFinished(
                    run_id=run_id,
                    status="Failed",
                    duration=duration,
                    error=f"{type(e).__name__}: {e}",
                )
            )
            raise
        finally:
            if self.connector:
                await self.connector.disconnect()

    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
        """Callback to handle incoming constraint messages."""
        try:
            # Basic validation, could be improved with a schema library
            constraint = GlobalConstraint(
                id=payload["id"],
                scope=payload["scope"],
                type=payload["type"],
                params=payload["params"],
                expires_at=payload.get("expires_at"),
            )
            self.constraint_manager.update_constraint(constraint)
        except (KeyError, TypeError) as e:
            # In a real system, we'd use a proper logger.
            # For now, print to stderr to avoid crashing the engine.
            print(
                f"[Engine] Error processing constraint on topic '{topic}': {e}"
            )
~~~~~

### 下一步建议
我们已经成功搭建了 `Engine` 接收外部约束指令的完整通道。然而，`ConstraintManager` 的 `check_permission` 方法目前仍然是一个返回 `True` 的占位符，这意味着即使我们接收到了暂停指令，任务也依然会继续执行。

因此，下一个至关重要的步骤是**在 `ConstraintManager` 中实现真正的约束评估逻辑**。

具体计划是：
1.  **实现全局暂停**: 修改 `check_permission` 方法，使其能够识别 `{"type": "pause", "scope": "global"}` 这样的约束。当此约束存在时，该方法应返回 `False`，从而有效地暂停所有新任务的提交。
2.  **实现任务级暂停**: 扩展逻辑，使其能够根据任务的属性（例如，任务名称）匹配 `scope` 字段（如 `"task:api_call"`），实现对特定类型任务的精准控制。

完成这一步后，我们的约束系统将首次具备实际的控制能力。如果你同意，我将着手制定这个计划。
