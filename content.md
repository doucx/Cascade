好的，遵从你的指示。我们现在正式开始第四阶段（Phase 4: Ecosystem Tooling）的开发。

这是一个正确的决策。在为 `Engine` 增加了强大的控制能力（并发、速率、TTL）之后，我们必须同步构建出色的操作工具，否则这些能力就如同屠龙之技，无处施展。

我们首先从一个最基础也最迫切的需求开始：让操作员能够**看到**当前系统中到底有哪些约束是激活的。这将通过为 `cs-observer` 增加一个 `status` 命令来实现。

## [WIP] feat(cli): 实现 'cs-observer status' 以显示当前激活的约束

### 用户需求
用户希望开始实施第四阶段的路线图，即构建和完善操作工具链。一个关键的需求是能够查询并显示当前在 MQTT Broker 上所有处于激活状态的约束。

### 评论
实现 `cs-observer status` 命令是第四阶段一个完美的起点。它利用 MQTT 的保留消息 (Retained Message) 特性，为操作员提供了一个即时的系统状态快照。这不仅极大地增强了系统的可观测性，也为我们刚刚实现的 TTL 功能提供了一个验证其是否按预期过期的绝佳调试工具。

### 目标
1.  在 `cascade-cli-observer` 包中，为 `app.py` 增加新的依赖导入 (`Table`, `GlobalConstraint`, `time` 等)。
2.  在 `app.py` 中实现一个新的 `status` 命令。
3.  该命令的逻辑将连接到 MQTT Broker，订阅 `cascade/constraints/#` 主题。
4.  利用订阅时 Broker 会立即下发所有保留消息的特性，在短暂等待后收集所有激活的约束。
5.  使用 `rich.Table` 将收集到的约束（包括其作用域、类型、参数和剩余 TTL）格式化并打印到控制台。
6.  命令执行完毕后应立即退出，而不是像 `watch` 命令一样持续监听。

### 基本原理
我们将创建一个一次性的 MQTT 客户端，它订阅通配符主题 `cascade/constraints/#`。由于所有 `cs-controller` 发布的约束都是保留消息，Broker 会在订阅建立的瞬间将所有这些消息一次性推送给客户端。我们通过一个短暂的 `asyncio.sleep` 来确保这个初始同步过程完成，然后断开连接并处理收集到的数据。通过计算当前时间与约束 `expires_at` 时间戳的差值，我们可以友好地向用户显示每个约束的剩余生命周期。

### 标签
#intent/build #flow/ready #priority/high 
#comp/cli #concept/ui #scope/ux 
#ai/instruct 
#task/domain/cli #task/object/cs-observer #task/action/feature-enhancement 
#task/state/begin

---

### Script

#### Acts 1: 为 `cs-observer` 增加必要的导入

我们需要 `rich.table`, `GlobalConstraint` 和 `time` 等模块来实现新功能。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
import asyncio
import typer
from cascade.common.messaging import bus
from .rendering import RichCliRenderer
from cascade.connectors.mqtt import MqttConnector

app = typer.Typer()
~~~~~
~~~~~python
import asyncio
import time
from datetime import datetime, timezone
import typer
from rich.console import Console
from rich.table import Table

from cascade.common.messaging import bus
from .rendering import RichCliRenderer
from cascade.connectors.mqtt import MqttConnector
from cascade.spec.constraint import GlobalConstraint

app = typer.Typer()
console = Console(stderr=True)
~~~~~

#### Acts 2: 实现 `status` 命令

我们将添加 `status` 命令及其异步辅助函数，该函数负责连接、收集和显示约束。

~~~~~act
patch_file
packages/cascade-cli-observer/src/cascade/cli/observer/app.py
~~~~~
~~~~~python
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        # The finally block in main_loop will handle graceful shutdown
        pass


def main():
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~
~~~~~python
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        # The finally block in main_loop will handle graceful shutdown
        pass


@app.command()
def status(
    hostname: str = typer.Option("localhost", help="MQTT broker hostname."),
    port: int = typer.Option(1883, help="MQTT broker port."),
):
    """
    Connect to the broker, query the current status of all constraints, and exit.
    """
    try:
        asyncio.run(_get_status(hostname=hostname, port=port))
    except KeyboardInterrupt:
        bus.info("observer.shutdown")


async def _get_status(hostname: str, port: int):
    """Core logic for the status command."""
    constraints: list[GlobalConstraint] = []

    async def on_status_message(topic, payload):
        if payload and isinstance(payload, dict):
            try:
                # Filter out any malformed or non-constraint messages
                if "scope" in payload and "type" in payload:
                    constraints.append(GlobalConstraint(**payload))
            except TypeError:
                pass  # Ignore malformed payloads

    connector = MqttConnector(hostname=hostname, port=port)
    bus.info("controller.connecting", hostname=hostname, port=port)
    await connector.connect()
    bus.info("controller.connected")
    await connector.subscribe("cascade/constraints/#", on_status_message)

    # Wait a short moment for all retained messages to arrive from the broker
    await asyncio.sleep(0.5)
    await connector.disconnect()
    bus.info("observer.shutdown")

    table = Table(title="[bold]Active Cascade Constraints[/bold]", title_justify="left")
    table.add_column("Scope", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Params", style="green")
    table.add_column("Expires In (s)", justify="right", style="yellow")

    now = time.time()
    if not constraints:
        console.print("[dim]No active constraints found.[/dim]")
        return

    for c in sorted(constraints, key=lambda x: x.scope):
        expires_in = ""
        if c.expires_at:
            delta = c.expires_at - now
            if delta > 0:
                expires_in = f"{delta:.1f}"
            else:
                expires_in = "[red]- (expired)[/red]"
        else:
            expires_in = "[dim]Never[/dim]"

        table.add_row(c.scope, c.type, str(c.params), expires_in)

    console.print(table)


def main():
    bus.set_renderer(RichCliRenderer(store=bus.store))
    app()


if __name__ == "__main__":
    main()
~~~~~

### 下一步建议
我们已经成功为 `cs-observer` 添加了 `status` 命令，迈出了第四阶段的第一步。

根据路线图，下一步的合理方向是继续增强 `cs-observer` 的**实时**观测能力。具体来说，我们可以：

1.  **增强 `watch` 命令**：使其能够解析并清晰地展示与约束相关的遥测事件，例如 `ConstraintApplied` 和 `TaskDeferredByConstraint`（这需要我们先在 `Engine` 中添加这些事件的遥tery）。
2.  **实现 `top` 命令**：创建一个类似 `htop` 的实时仪表盘，显示当前各类任务的并发数、成功率和失败率。

我建议我们先从增强 `watch` 命令开始，因为它能提供更精细的实时反馈，帮助我们更好地理解和调试 `Engine` 的动态行为。
