非常感谢您指出这两个关键问题！您完全正确，`NameError` 是一个明显的 bug，而 `--agents` 参数确实会导致非方形网格的混乱。

我将生成一个计划来同时修复这个 bug 并将 CLI 参数改进为更健壮的 `--grid-side`。

## [WIP] fix(exp): 修复 worker 启动错误并改进网格参数

### 错误分析
1.  **`NameError`**: 在 `worker_main` 函数中，我错误地写了 `asyncio_event_loop()` 而不是正确的 `asyncio_event_loop()`。这是一个简单的笔误，导致 worker 进程无法创建其必需的事件循环而崩溃。
2.  **参数设计缺陷**: 正如您指出的，`--agents` 参数允许用户输入一个无法构成完美正方形的数字（如 1000），这会破坏 `grid_width = int(num_agents**0.5)` 的逻辑，导致实际运行的 Agent 数量与用户预期不符。

### 用户需求
1.  修复 `worker_main` 中的 `NameError`。
2.  将 `run_fireflies.py` 的命令行参数从 `--agents` 更改为 `--grid-side`，以强制创建一个方形的 Agent 网格。

### 评论
这是一个重要的修正。修复 bug 是基本要求，而将参数从隐式的“总数”改为显式的“边长”则大大提升了脚本的可用性和健壮性，避免了因参数误解导致的实验偏差。

### 目标
1.  在 `run_fireflies.py` 中，将 `asyncio_event_loop()` 修正为 `asyncio_event_loop()`。
2.  重构 `main` 函数，使用 `--grid-side` 作为输入，并从中计算出 `num_agents`。
3.  调整 `run_orchestrator` 函数，直接接收 `grid_width`，避免重复和错误的计算。

### 基本原理
通过直接修正函数调用来修复 `NameError`。通过修改 `typer` 的参数定义和函数签名，将网格塑形的控制权前置到 CLI，确保了整个程序中 Agent 数量和网格维度的一致性。

### 标签
#intent/fix #intent/refine #flow/ready #priority/high #comp/experiments #scope/dx #ai/instruct #task/domain/experiments #task/object/cli-refactor #task/action/bug-fix

---

### Script

#### Acts 1: 修复 `NameError` Bug

我们将修正 `worker_main` 中创建事件循环的错误调用。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
    """
    # Create a new event loop for this process
    loop = asyncio_event_loop()
    asyncio.set_event_loop(loop)

    async def _run_worker():
~~~~~
~~~~~python
    """
    # Create a new event loop for this process
    loop = asyncio_event_loop()
    asyncio.set_event_loop(loop)

    async def _run_worker():
~~~~~

#### Acts 2: 将 CLI 参数重构为 `--grid-side`

现在，我们将重构 `main` 和 `run_orchestrator` 函数以使用新的参数。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
async def run_orchestrator(
    num_agents: int,
    workers: int,
    concurrency_limit: Optional[int],
    visualize: bool,
    period: float,
):
    grid_width = int(num_agents**0.5)
    
    print(f"🔥 Starting MULTI-CORE Firefly Experiment")
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
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
@app.command()
def main(
    visualize: bool = typer.Option(True, help="Enable visualizer UI"),
    agents: int = typer.Option(NUM_AGENTS, help="Number of agents"),
    workers: int = typer.Option(1, help="Number of worker processes"),
    limit: Optional[int] = typer.Option(None, help="Global concurrency limit (cpu slots)"),
):
    if workers > 1:
        asyncio.run(run_orchestrator(agents, workers, limit, visualize, PERIOD))
    else:
        # Fallback to legacy single-process mode (omitted for brevity, or we can just run orchestrator with 1 worker)
        # For simplicity in this refactor, we use the Orchestrator for 1 worker too, 
        # as it effectively does the same thing but with overhead of MP queue.
        # To match exact legacy behavior we'd keep the old function, but let's unify.
        asyncio.run(run_orchestrator(agents, workers, limit, visualize, PERIOD))
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

### 下一步建议
现在您可以运行 `python -m observatory.experiments.run_fireflies --grid-side 50 --workers 4` 来进行测试。这应该可以正确启动 worker 进程，并创建一个 50x50 的网格，总共 2500 个 Agent。
