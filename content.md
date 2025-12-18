好的，我将分析当前的项目状态，并根据《Phase 3 (Refined) & Phase 4 并行开发路线图》文档，选取**里程碑 3.1: 精准控制 (Targeted Control)** 作为本次任务的核心，并生成一个完整的实施计划。

这是一个关键的里程碑，它将系统的控制能力从“全局”提升到了“任务级”，是实现“自适应执行环境”愿景的基础。为了实现这一点，我们需要同步修改引擎和 CLI 工具。

## [WIP] feat(control): 实现任务级暂停与恢复机制

### 用户需求
根据项目路线图，需要实现里程碑 3.1，为 Cascade 系统引入任务级的精准控制能力。具体需求如下：
1.  **引擎能力**: `Engine` 必须能够理解并执行针对特定任务范围（如 `task:api_call`）的 `pause` 约束。
2.  **工具能力**: `cs-controller` CLI 工具需要增加一个 `resume` 命令，用于解除之前施加的 `pause` 约束。
3.  **协议健壮性**: `pause` 和 `resume` 的实现需要依赖 MQTT 的保留消息 (Retained Message) 机制，以确保控制状态的持久性。

### 评论
这是一个对系统可操作性的重大改进。它将 Cascade 从一个纯粹的“执行引擎”转变为一个可被外部实时管理的“受控系统”，为实现更高级的运维模式（如蓝绿部署、金丝雀发布中的流量控制、紧急止损等）奠定了基础。通过并行开发 `cs-controller`，我们确保了引擎的新能力能够立刻转化为对开发者和运维人员有价值的工具。

### 目标
1.  **增强 `MqttConnector`**: 修改 `publish` 方法，使其支持 MQTT 的 `retain` 标志，这是实现持久化控制状态的关键。
2.  **增强 `cs-controller`**:
    *   更新 `pause` 命令，使其发布的约束消息成为保留消息。
    *   创建一个新的 `resume` 命令，它通过向同一主题发布一条空的保留消息来清除先前的 `pause` 状态。
    *   为新命令添加对应的用户反馈消息。
3.  **增强 `ConstraintManager`**: 增加一个 `remove_constraints_by_scope` 方法，允许 `Engine` 响应 `resume` 指令。
4.  **增强 `Engine`**: 更新其 MQTT 回调逻辑 (`_on_constraint_update`)，使其能够处理空消息负载（代表 `resume`），并调用 `ConstraintManager` 的新方法来移除约束。
5.  **增强 `PauseConstraintHandler`**: 更新其 `check_permission` 逻辑，以正确解析并匹配任务级范围（`task:<task_name>`）。

### 基本原理
我们将利用 MQTT 的 **保留消息 (Retained Message)** 机制作为实现“状态控制”的基石。
*   当 `cs-controller pause --task api_call` 执行时，它会向 `cascade/constraints/task/api_call` 主题发布一条**带有 `retain=True` 标志的**约束消息。Broker 会持久化这条消息。任何新连接到此主题的 `Engine` 都会立即收到这个“暂停”状态。
*   当 `cs-controller resume --task api_call` 执行时，它会向同一主题发布一条**空的、`retain=True` 的**消息。根据 MQTT 规范，这会清除该主题上先前的保留消息。
*   `Engine` 端会订阅 `cascade/constraints/#`。当收到空消息时，它会识别出这是一个“解除”信号，并从其内部的 `ConstraintManager` 中移除所有与该主题范围匹配的约束，从而恢复任务执行。

这种设计将控制状态的“真理之源”放在了消息代理 (Broker) 上，极大地解耦了控制者和执行者。

### 标签
#intent/build #flow/ready #priority/high
#comp/runtime #comp/cli #comp/interfaces
#concept/executor #scope/api #scope/ux
#ai/instruct
#task/domain/control #task/object/constraint-system #task/action/refinement #task/state/begin

---
### Script

#### Acts 1: 增强 MqttConnector 与其协议以支持保留消息

首先，我们需要让核心的 `MqttConnector` 和 `Connector` 协议支持 `retain` 标志。

~~~~~act
patch_file
packages/cascade-interfaces/src/cascade/interfaces/protocols.py
~~~~~
~~~~~python
    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """Publishes a message (e.g., a telemetry event) to a specific topic."""
        ...
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Dict[str, Any], qos: int = 0, retain: bool = False
    ) -> None:
        """Publishes a message (e.g., a telemetry event) to a specific topic."""
        ...
~~~~~
~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
    async def publish(self, topic: str, payload: Dict[str, Any], qos: int = 0) -> None:
        """
        Publishes a message in a non-blocking, fire-and-forget manner.
        """
        if not self._client:
            logger.warning("Attempted to publish without an active MQTT connection.")
            return

        async def _do_publish():
            try:
                json_payload = json.dumps(payload)
                await self._client.publish(topic, payload=json_payload, qos=qos)
            except Exception as e:
                # Per Fail-Silent Telemetry principle, we log errors but don't propagate them.
                logger.error(f"Failed to publish MQTT message to topic '{topic}': {e}")

        asyncio.create_task(_do_publish())
~~~~~
~~~~~python
    async def publish(
        self, topic: str, payload: Any, qos: int = 0, retain: bool = False
    ) -> None:
        """
        Publishes a message in a non-blocking, fire-and-forget manner.
        """
        if not self._client:
            logger.warning("Attempted to publish without an active MQTT connection.")
            return

        async def _do_publish():
            try:
                # Support both dicts (for JSON) and empty strings (for clearing retained)
                if isinstance(payload, dict):
                    final_payload = json.dumps(payload)
                else:
                    final_payload = payload

                await self._client.publish(
                    topic, payload=final_payload, qos=qos, retain=retain
                )
            except Exception as e:
                # Per Fail-Silent Telemetry principle, we log errors but don't propagate them.
                logger.error(f"Failed to publish MQTT message to topic '{topic}': {e}")

        asyncio.create_task(_do_publish())
~~~~~

#### Acts 2: 在 Controller 中实现 `resume` 命令并更新 `pause`

现在我们为 `cs-controller` 添加 `resume` 功能，并让 `pause` 使用保留消息。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
async def _publish_pause(scope: str, hostname: str, port: int):
    """Core logic for publishing a pause constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        # Create a unique, descriptive ID for the constraint
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id, scope=scope, type="pause", params={}
        )

        # Convert to dictionary for JSON serialization
        payload = asdict(constraint)

        # Publish to a structured topic based on scope
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.publishing", scope=scope, topic=topic)
        # The connector's publish is fire-and-forget
        await connector.publish(topic, payload)

        # In a real fire-and-forget, we can't be sure it succeeded,
        # but for UX we assume it did if no exception was raised.
        # Give a brief moment for the task to be sent.
        await asyncio.sleep(0.1)
        bus.info("controller.publish_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
~~~~~
~~~~~python
async def _publish_pause(scope: str, hostname: str, port: int):
    """Core logic for publishing a pause constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        # Create a unique, descriptive ID for the constraint
        constraint_id = f"pause-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id, scope=scope, type="pause", params={}
        )

        # Convert to dictionary for JSON serialization
        payload = asdict(constraint)

        # Publish to a structured topic based on scope
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.publishing", scope=scope, topic=topic)
        # The connector's publish is fire-and-forget, now with retain=True
        await connector.publish(topic, payload, retain=True)

        # In a real fire-and-forget, we can't be sure it succeeded,
        # but for UX we assume it did if no exception was raised.
        # Give a brief moment for the task to be sent.
        await asyncio.sleep(0.1)
        bus.info("controller.publish_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


async def _publish_resume(scope: str, hostname: str, port: int):
    """Core logic for publishing a resume (clear constraint) command."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.resuming", scope=scope, topic=topic)
        # Publishing an empty retained message clears the previous one
        await connector.publish(topic, "", retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.resume_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
        help="The scope to pause (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
~~~~~
~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()
~~~~~
~~~~~python
@app.command()
def resume(
    scope: str = typer.Argument(
        "global",
        help="The scope to resume (e.g., 'global', 'project:etl', 'task:api_call').",
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'resume' command to the MQTT broker.
    This clears any 'pause' constraint for the specified scope, allowing
    tasks to be scheduled again.
    """
    try:
        asyncio.run(_publish_resume(scope=scope, hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


def main():
    bus.set_renderer(CliRenderer(store=bus.store))
    app()
~~~~~
~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
~~~~~
~~~~~json
    "controller.publishing": "📡 Publishing constraint for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_success": "✅ Constraint published successfully.",
    "controller.error": "❌ An error occurred: {error}"
}
~~~~~
~~~~~
json
    "controller.publishing": "📡 Publishing constraint for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_success": "✅ Constraint published successfully.",
    "controller.resuming": "📡 Publishing resume command for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.resume_success": "✅ Resume command published successfully.",
    "controller.error": "❌ An error occurred: {error}"
}
~~~~~

#### Acts 3: 更新 Engine 和 ConstraintManager 以响应 `resume`

接下来，我们需要让 `Engine` 能理解 `resume` 信号，并让 `ConstraintManager` 具备移除约束的能力。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/manager.py
~~~~~
~~~~~python
    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

    def check_permission(self, task: Node) -> bool:
~~~~~
~~~~~python
    def update_constraint(self, constraint: GlobalConstraint) -> None:
        """Adds a new constraint or updates an existing one."""
        self._constraints[constraint.id] = constraint

    def remove_constraints_by_scope(self, scope: str) -> None:
        """Removes all constraints that match the given scope."""
        ids_to_remove = [
            cid for cid, c in self._constraints.items() if c.scope == scope
        ]
        for cid in ids_to_remove:
            del self._constraints[cid]

    def check_permission(self, task: Node) -> bool:
~~~~~
~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
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
                f"[Engine] Error processing constraint on topic '{topic}': {e}",
                file=sys.stderr,
            )
~~~~~
~~~~~python
    async def _on_constraint_update(self, topic: str, payload: Dict[str, Any]):
        """Callback to handle incoming constraint messages."""
        # An empty payload signifies a cleared retained message (i.e., a resume command)
        if not payload:
            try:
                # Reconstruct scope from topic, e.g., cascade/constraints/task/api_call -> task:api_call
                scope_parts = topic.split("/")[2:]
                scope = ":".join(scope_parts)
                if scope:
                    self.constraint_manager.remove_constraints_by_scope(scope)
                return
            except Exception as e:
                print(
                    f"[Engine] Error processing resume command on topic '{topic}': {e}",
                    file=sys.stderr,
                )
                return

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
                f"[Engine] Error processing constraint on topic '{topic}': {e}",
                file=sys.stderr,
            )
~~~~~
~~~~~act
patch_file
packages/cascade-connector-mqtt/src/cascade/connectors/mqtt/connector.py
~~~~~
~~~~~python
                try:
                    # aiomqtt payload can be bytes, bytearray, etc.
                    if isinstance(payload_bytes, (bytes, bytearray)):
                        payload_str = payload_bytes.decode("utf-8")
                    else:
                        payload_str = str(payload_bytes)

                    data = json.loads(payload_str)

                    # Execute callback (fire and forget, or await?)
~~~~~
~~~~~python
                try:
                    # aiomqtt payload can be bytes, bytearray, etc.
                    if isinstance(payload_bytes, (bytes, bytearray)):
                        payload_str = payload_bytes.decode("utf-8")
                    else:
                        payload_str = str(payload_bytes)
                    
                    # If the payload is empty (resume command), pass an empty dict
                    if not payload_str:
                        data = {}
                    else:
                        data = json.loads(payload_str)

                    # Execute callback (fire and forget, or await?)
~~~~~

#### Acts 4: 实现任务级范围匹配

最后，我们让 `PauseConstraintHandler` 能够理解 `task:` 范围。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/constraints/handlers.py
~~~~~
~~~~~python
class PauseConstraintHandler(ConstraintHandler):
    """
    Handles the 'pause' constraint type.
    It can pause execution globally or for a specific task.
    """

    def handles_type(self) -> str:
        return "pause"

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Returns False (permission denied) if the task matches the constraint's scope.
        """
        scope = constraint.scope

        # Global scope matches everything
        if scope == "global":
            return False

        # Task-specific scope
        if scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                return False

        # Project-specific scope (placeholder for future implementation)
        # if scope.startswith("project:"):
        #     ...

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True
~~~~~
~~~~~python
class PauseConstraintHandler(ConstraintHandler):
    """
    Handles the 'pause' constraint type.
    It can pause execution globally or for a specific task.
    """

    def handles_type(self) -> str:
        return "pause"

    def check_permission(
        self, task: Node, constraint: GlobalConstraint, manager: "ConstraintManager"
    ) -> bool:
        """
        Returns False (permission denied) if the task matches the constraint's scope.
        """
        scope = constraint.scope

        # Global scope matches everything
        if scope == "global":
            return False

        # Task-specific scope
        if scope.startswith("task:"):
            target_task_name = scope.split(":", 1)[1]
            if task.name == target_task_name:
                return False

        # Project-specific scope (placeholder for future implementation)
        # if scope.startswith("project:"):
        #     ...

        # If no match, this constraint doesn't apply to this task, so it is permitted.
        return True
~~~~~

### 下一步建议
我们已经完成了核心功能的实现。现在最关键的一步是编写集成测试来验证这个新的控制回路。

我建议在 `tests/py/runtime/test_engine_constraints.py` 文件中增加一个新的测试用例 `test_engine_pauses_specific_task_and_resumes`。该测试应遵循以下逻辑：

1.  定义一个 A -> B -> C 的工作流。
2.  启动 `Engine`。
3.  等待任务 A 完成。
4.  使用 Mock Connector 注入一个针对 `task:task_b` 的 `pause` 约束。
5.  断言任务 B **没有**被启动，而任务 C 也因此被阻塞。
6.  注入一个针对 `task:task_b` 的 `resume` 命令（即发布空消息）。
7.  断言任务 B **现在被启动并完成**，随后任务 C 也完成。
8.  整个测试的断言都应基于 `SpySubscriber` 捕获的事件流，以遵循**“验证意图而非实现”**的测试原则。

如果你同意，我将为你生成实现该测试的计划。
