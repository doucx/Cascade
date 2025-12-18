好的，我们已经完成了核心引擎能力的构建和验证。现在，我们将按照路线图，为这个新能力构建对应的操作工具，完成里程碑 3.2。

我将为您生成一个计划，在 `cs-controller` 中实现 `set-limit` 命令。

## [WIP] feat(cli-controller): 实现 set-limit --concurrency 命令

### 用户需求
在 `cs-controller` CLI 工具中添加一个新的 `set-limit` 命令，允许操作员通过 `--concurrency` 选项发布并发限制约束。

### 评论
这是“共生演进”原则的体现。我们刚刚在引擎中实现了一种新的控制能力，现在立刻就为它创建一个操作界面。这个 CLI 工具是连接操作员意图与系统底层能力的桥梁，使复杂的并发管理变得简单可控。

### 目标
1.  在 `cascade-cli-controller/src/cascade/cli/controller/app.py` 中添加一个 `set_limit` Typer 命令。
2.  该命令接受 `--scope` 和 `--concurrency` 参数。
3.  实现一个新的 `_publish_limit` 异步函数，负责构建 `type="concurrency"` 的 `GlobalConstraint`。
4.  将此约束作为保留消息发布到正确的 MQTT 主题。
5.  在 `cli_messages.json` 中为新命令添加相应的用户反馈消息。

### 基本原理
我们将复用 `_publish_pause` 函数的模式，创建一个新的 `_publish_limit` 函数。该函数将接收 `scope` 和 `limit`，构造一个包含 `{"limit": ...}` 参数的 `GlobalConstraint` 对象，序列化为 JSON，并将其发布到 `cascade/constraints/{scope}` 主题上，同时设置 `retain=True` 标志。

### 标签
#intent/build #flow/ready #priority/high #comp/cli #concept/ui #scope/ux #ai/instruct #task/domain/core #task/object/concurrency-control #task/action/implementation #task/state/continue

---

### Script

#### Acts 1: 在 Controller 中添加 set-limit 命令

我们将修改 `app.py`，添加新的 `_publish_limit` 异步函数和 `set_limit` Typer 命令。

~~~~~act
patch_file
packages/cascade-cli-controller/src/cascade/cli/controller/app.py
~~~~~
~~~~~python
    finally:
        await connector.disconnect()


@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
~~~~~
~~~~~python
    finally:
        await connector.disconnect()


async def _publish_limit(scope: str, concurrency: int, hostname: str, port: int):
    """Core logic for publishing a concurrency limit constraint."""
    connector = MqttConnector(hostname=hostname, port=port)
    try:
        bus.info("controller.connecting", hostname=hostname, port=port)
        await connector.connect()
        bus.info("controller.connected")

        constraint_id = f"concurrency-{scope}-{uuid.uuid4().hex[:8]}"
        constraint = GlobalConstraint(
            id=constraint_id,
            scope=scope,
            type="concurrency",
            params={"limit": concurrency},
        )

        payload = asdict(constraint)
        topic = f"cascade/constraints/{scope.replace(':', '/')}"

        bus.info("controller.publishing_limit", scope=scope, topic=topic, limit=concurrency)
        await connector.publish(topic, payload, retain=True)

        await asyncio.sleep(0.1)
        bus.info("controller.publish_limit_success")

    except Exception as e:
        bus.error("controller.error", error=e)
    finally:
        await connector.disconnect()


@app.command()
def set_limit(
    scope: str = typer.Option(
        ..., "--scope", help="The scope to apply the limit to (e.g., 'global', 'task:api_call')."
    ),
    concurrency: int = typer.Option(
        ..., "--concurrency", help="The maximum number of concurrent tasks."
    ),
    hostname: str = typer.Option("localhost", "--host", help="MQTT broker hostname."),
    port: int = typer.Option(1883, "--port", help="MQTT broker port."),
):
    """
    Publish a 'concurrency' constraint to the MQTT broker.
    """
    try:
        asyncio.run(
            _publish_limit(scope=scope, concurrency=concurrency, hostname=hostname, port=port)
        )
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


@app.command()
def pause(
    scope: str = typer.Argument(
        "global",
~~~~~

#### Acts 2: 添加用户反馈消息

为了提供清晰的用户体验，我们在 `cli_messages.json` 中为新命令添加反馈文本。

~~~~~act
patch_file
packages/cascade-common/src/cascade/common/locales/en/cli_messages.json
~~~~~
~~~~~json
    "controller.publishing": "📡 Publishing constraint for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_success": "✅ Constraint published successfully.",
    "controller.resuming": "📡 Publishing resume command for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.resume_success": "✅ Resume command published successfully.",
    "controller.error": "❌ An error occurred: {error}"
}
~~~~~
~~~~~json
    "controller.publishing": "📡 Publishing 'pause' constraint for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_success": "✅ Pause constraint published successfully.",
    "controller.publishing_limit": "📡 Publishing concurrency limit of [bold magenta]{limit}[/bold magenta] for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.publish_limit_success": "✅ Concurrency limit published successfully.",
    "controller.resuming": "📡 Publishing resume command for scope '[bold cyan]{scope}[/bold cyan]' to topic '[bold yellow]{topic}[/bold yellow]'...",
    "controller.resume_success": "✅ Resume command published successfully.",
    "controller.error": "❌ An error occurred: {error}"
}
~~~~~

### 下一步建议
我们已经完成了并发管理里程碑的引擎能力和配套工具。现在，最激动人心的时刻到了：**端到端验证**。

我建议您：
1.  启动一个运行 `test_engine_concurrency.py` 中 `test_concurrency_constraint_on_map` 工作流的 Cascade 脚本。
2.  在另一个终端，使用我们刚刚创建的 `cs-controller set-limit --scope task:slow_task --concurrency 1` 命令。
3.  同时，使用 `cs-observer watch` 观察任务执行的遥测数据。

您应该能实时地看到任务从并行执行变为串行执行，直观地验证我们整个系统的闭环。
