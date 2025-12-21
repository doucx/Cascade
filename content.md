好的，这是一个非常合理的 DX (开发者体验) 改进。将核心物理参数暴露为命令行选项，可以让我们在不修改代码的情况下，快速进行“超参数”搜索和调试。

我将为您生成一个计划，将 `period`, `nudge`, `duration` 等关键参数添加到 `run_fireflies.py` 的命令行界面中。

## [WIP] feat(exp): 将核心仿真参数暴露为 CLI 选项

### 用户需求
为了方便调试和参数调优，需要将 `run_fireflies.py` 脚本中的核心仿真参数（如 `period`, `nudge`, `duration_seconds` 等）作为命令行选项暴露出来。

### 评论
这是一个重要的可用性改进，它将一个“硬编码的实验脚本”转变为一个“灵活的仿真工具”。这使得非开发人员也能方便地运行不同的实验场景，并极大地加速了我们对 Kuramoto 模型不同参数下涌现行为的探索。

### 目标
1.  修改 `run_fireflies.py` 的 `main` 函数，使用 `typer.Option` 添加 `--period`, `--nudge`, `--duration`, 和 `--decay-duty-cycle` 参数。
2.  确保这些参数能被正确地传递到 `run_orchestrator` 和 `worker_main` 函数中，并最终影响 Agent 的行为。

### 基本原理
通过扩展 `typer` 应用的接口，我们可以利用其内置的类型检查、默认值和帮助文本生成功能，以一种健壮且自文档化的方式增强脚本的灵活性。参数将通过函数调用链逐层传递，从 `main` -> `run_orchestrator` -> `worker_main` -> `firefly_agent`。

### 标签
#intent/refine #flow/ready #priority/medium #comp/experiments #scope/dx #ai/instruct #task/domain/experiments #task/object/cli-refactor #task/action/enhancement #task/state/continue

---

### Script

#### Acts 1: 更新 `main` 函数以接受更多参数

我们将扩展 `main` 函数的签名，并更新对 `run_orchestrator` 的调用。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
@app.command()
def main(
    visualize: bool = typer.Option(True, help="Enable visualizer UI"),
    grid_side: int = typer.Option(GRID_SIDE, help="Side length of the square agent grid."),
    workers: int = typer.Option(1, help="Number of worker processes"),
    limit: Optional[int] = typer.Option(None, help="Global concurrency limit (per process)"),
):
    num_agents = grid_side * grid_side
    asyncio.run(run_orchestrator(num_agents, grid_side, workers, limit, visualize, PERIOD))
~~~~~
~~~~~python
@app.command()
def main(
    visualize: bool = typer.Option(True, help="Enable visualizer UI"),
    grid_side: int = typer.Option(GRID_SIDE, help="Side length of the square agent grid."),
    workers: int = typer.Option(1, help="Number of worker processes"),
    limit: Optional[int] = typer.Option(None, help="Global concurrency limit (per process)"),
    period: float = typer.Option(PERIOD, help="Oscillation period for agents."),
    nudge: float = typer.Option(0.2, help="Coupling strength (phase nudge)."),
    duration: float = typer.Option(300.0, help="Duration of the experiment in seconds."),
    decay_duty_cycle: float = typer.Option(0.3, help="Flash visibility duration as a fraction of period."),
):
    num_agents = grid_side * grid_side
    asyncio.run(run_orchestrator(
        num_agents=num_agents,
        grid_width=grid_side,
        workers=workers,
        concurrency_limit=limit,
        visualize=visualize,
        period=period,
        nudge=nudge,
        duration_seconds=duration,
        decay_duty_cycle=decay_duty_cycle,
    ))
~~~~~

#### Acts 2: 更新 `run_orchestrator` 以接受和使用新参数

`run_orchestrator` 需要接收这些参数，并将它们传递给 `worker_main` 和可视化组件。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
async def run_orchestrator(
    num_agents: int,
    grid_width: int,
    workers: int,
    concurrency_limit: Optional[int],
    visualize: bool,
    period: float,
):
    print(f"🔥 Starting MULTI-CORE Firefly Experiment")
    print(f"   - Agents: {num_agents} ({grid_width}x{grid_width})")
~~~~~
~~~~~python
async def run_orchestrator(
    num_agents: int,
    grid_width: int,
    workers: int,
    concurrency_limit: Optional[int],
    visualize: bool,
    period: float,
    nudge: float,
    duration_seconds: float,
    decay_duty_cycle: float,
):
    print(f"🔥 Starting MULTI-CORE Firefly Experiment")
    print(f"   - Agents: {num_agents} ({grid_width}x{grid_width})")
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    if visualize:
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * 0.3),
        )
        status_bar = StatusBar(initial_status={"Agents": num_agents, "Workers": workers})
~~~~~
~~~~~python
    if visualize:
        grid_view = GridView(
            width=grid_width,
            height=grid_width,
            palette_func=Palettes.firefly,
            decay_per_second=1 / (period * decay_duty_cycle),
        )
        status_bar = StatusBar(initial_status={"Agents": num_agents, "Workers": workers, "Period": period, "Nudge": nudge})
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        p = mp.Process(
            target=worker_main,
            args=(
                w_id, indices, uplink_queue, concurrency_limit,
                grid_width, grid_width, period, 0.2
            )
        )
        p.start()
        processes.append(p)
~~~~~
~~~~~python
        p = mp.Process(
            target=worker_main,
            args=(
                w_id, indices, uplink_queue, concurrency_limit,
                grid_width, grid_width, period, nudge
            )
        )
        p.start()
        processes.append(p)
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    try:
        while any(p.is_alive() for p in processes):
            # We assume high throughput, so we batch read or read continuously
            # Using run_in_executor to avoid blocking the main loop with queue.get
            try:
                # Non-blocking get from queue
                while not uplink_queue.empty():
                    topic, payload = uplink_queue.get_nowait()
                    # Re-publish to local bus (driving the UI)
                    await main_connector.publish(topic, payload)
                
                # Yield to let UI render
                await asyncio.sleep(0.01)
            except Exception:
                await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        pass
    finally:
~~~~~
~~~~~python
    # 4. Telemetry Pump Loop & Experiment Timer
    print("🚀 Workers launched. Bridging telemetry...")
    
    start_time = time.time()
    try:
        while time.time() - start_time < duration_seconds:
            if not any(p.is_alive() for p in processes):
                print("🛑 All workers terminated prematurely.")
                break
            try:
                while not uplink_queue.empty():
                    topic, payload = uplink_queue.get_nowait()
                    await main_connector.publish(topic, payload)
                
                await asyncio.sleep(0.01)
            except Exception:
                await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        pass
    finally:
~~~~~

#### Acts 3: 更新 `worker_main` 以接受新参数

最后，确保 `worker_main` 函数能接收 `nudge` 参数并将其传递给 Agent。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
            workflow = firefly_agent(
                agent_id=i,
                initial_phase=initial_phase,
                period=period,
                nudge=nudge,
                neighbors=my_neighbors,
                my_channel=my_channel,
                connector=connector,
                refractory_period=period * 0.2,
            )

            if local_limit:
~~~~~
~~~~~python
            workflow = firefly_agent(
                agent_id=i,
                initial_phase=initial_phase,
                period=period,
                nudge=nudge,
                neighbors=my_neighbors,
                my_channel=my_channel,
                connector=connector,
                refractory_period=period * 0.2,
            )

            if local_limit:
~~~~~

### 下一步建议
现在您可以使用更丰富的命令行选项来运行实验了，例如：

`python -m observatory.experiments.run_fireflies --grid-side 30 --workers 4 --period 2.5 --nudge 0.5 --duration 60`

这将启动一个 30x30 的网格，在 4 个核心上运行，Agent 的周期为 2.5 秒，耦合强度为 0.5，总共运行 60 秒。
