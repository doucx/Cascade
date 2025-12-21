简要回答：
好的，我将在 `Engine` 中支持注入共享的 `ResourceManager`，并更新 `run_fireflies.py` 以支持通过 CLI 选项 `--concurrency-limit` 手动设置全局并发限制。

## [WIP] feat(exp): 在 run_fireflies 中支持手动并发限制

### 用户需求
在 `run_fireflies.py` 实验中添加一个命令行选项，允许用户手动指定全局并发限制，以验证 VM 模式下的资源调度和约束检查是否生效。这需要多个 Agent（每个有独立的 Engine）共享同一个资源管理器。

### 评论
这是一个非常实用的功能验证需求。它不仅测试了 VM 的资源集成，还隐含地推动了 Engine 架构向支持“多租户/共享资源”的方向演进。通过显式注入 `ResourceManager`，我们可以打破 Engine 之间的资源隔离墙。

### 目标
1.  修改 `Engine.__init__`，允许从外部注入 `ResourceManager` 实例。
2.  重构 `run_fireflies.py`，使用 `typer` 处理命令行参数，并实现跨 Engine 的资源共享和约束应用。

### 基本原理
目前的 `Engine` 在初始化时总是创建一个新的、私有的 `ResourceManager`，导致无法在多个 Engine 实例间实现全局限流。通过允许注入，我们可以创建一个全局的 Manager 并在所有 Agent 间共享。同时，利用 `LazyResult.with_constraints` 方法，我们可以动态地为每个 Agent 的任务附加资源需求。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #comp/experiments #scope/api #ai/instruct #task/domain/runtime #task/object/engine #task/action/refactor #task/state/continue

---

### Script

#### Acts 1: 允许 Engine 注入 ResourceManager

首先，我们修改 `Engine` 的构造函数，使其接受一个可选的 `resource_manager` 参数。

~~~~~act
patch_file
packages/cascade-runtime/src/cascade/runtime/engine.py
~~~~~
~~~~~python
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend
        self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
~~~~~
~~~~~python
        state_backend_factory: Callable[[str], StateBackend] = None,
        system_resources: Optional[Dict[str, Any]] = None,
        connector: Optional[Connector] = None,
        cache_backend: Optional[Any] = None,
        resource_manager: Optional[ResourceManager] = None,
    ):
        self.solver = solver
        self.executor = executor
        self.bus = bus
        self.connector = connector
        # Default to InMemory factory if none provided
        self.state_backend_factory = state_backend_factory or (
            lambda run_id: InMemoryStateBackend(run_id)
        )
        self.cache_backend = cache_backend
        
        if resource_manager:
            self.resource_manager = resource_manager
            # If system_resources is also provided, we update the injected manager
            if system_resources:
                self.resource_manager.set_capacity(system_resources)
        else:
            self.resource_manager = ResourceManager(capacity=system_resources)

        # Setup constraint manager with default handlers
        self.constraint_manager = ConstraintManager(self.resource_manager)
~~~~~

#### Acts 2: 更新 run_fireflies.py 支持 CLI 和资源限制

现在我们重构实验脚本。我们将引入 `typer`，创建共享的资源管理器，并在构建 Workflow 时应用约束。

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
import asyncio
import random
from typing import Dict, Any, List
import time

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator
from observatory.networking.direct_channel import DirectChannel

# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar

# --- Constants ---
GRID_SIDE = 30
NUM_AGENTS = GRID_SIDE * GRID_SIDE  # 2500
PERIOD = 5.0  # Slowed down to allow CPU to catch up with 2500 agents
~~~~~
~~~~~python
import asyncio
import random
from typing import Dict, Any, List, Optional
import time
import typer

import cascade as cs
from cascade.connectors.local import LocalBusConnector
from cascade.spec.resource import resource
from cascade.runtime.resource_manager import ResourceManager

from observatory.agents.kuramoto import firefly_agent
from observatory.monitors.convergence import ConvergenceMonitor
from observatory.monitors.aggregator import MetricsAggregator
from observatory.networking.direct_channel import DirectChannel

# Visualization
from observatory.visualization.palette import Palettes
from observatory.visualization.raw_app import RawTerminalApp as TerminalApp
from observatory.visualization.grid import GridView
from observatory.visualization.status import StatusBar

# --- Constants ---
GRID_SIDE = 30
NUM_AGENTS = GRID_SIDE * GRID_SIDE  # 2500
PERIOD = 5.0  # Slowed down to allow CPU to catch up with 2500 agents

app = typer.Typer()
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
async def run_experiment(
    num_agents: int = NUM_AGENTS,
    period: float = PERIOD,
    nudge: float = 0.2,
    duration_seconds: float = 3000.0,
    visualize: bool = True,
    decay_duty_cycle: float = 0.3,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    grid_width = int(num_agents**0.5)
    print(
        f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents ({grid_width}x{grid_width})..."
    )

    # 1. Initialize Shared Bus
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # --- Setup Monitor & Visualizer ---
~~~~~
~~~~~python
async def run_experiment(
    num_agents: int = NUM_AGENTS,
    period: float = PERIOD,
    nudge: float = 0.2,
    duration_seconds: float = 3000.0,
    visualize: bool = True,
    decay_duty_cycle: float = 0.3,
    concurrency_limit: Optional[int] = None,
):
    """
    Sets up and runs the firefly synchronization experiment.
    """
    grid_width = int(num_agents**0.5)
    print(
        f"🔥 Starting {'VISUAL' if visualize else 'HEADLESS'} firefly experiment with {num_agents} agents ({grid_width}x{grid_width})..."
    )
    if concurrency_limit:
        print(f"⚠️  Global Concurrency Limit: {concurrency_limit} slots")

    # 1. Initialize Shared Bus and Resources
    LocalBusConnector._reset_broker_state()
    connector = LocalBusConnector()
    await connector.connect()

    # Shared Resource Manager for Global Limits
    shared_resource_manager = None
    if concurrency_limit:
        # Define a global 'cpu_slot' resource
        shared_resource_manager = ResourceManager(capacity={"cpu_slot": concurrency_limit})

    # --- Setup Monitor & Visualizer ---
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None,
        )
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=period,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=connector,
            refractory_period=period * 0.2,
        )

        # Enable VM execution for TailCall support
        agent_tasks.append(engine.run(agent_workflow, use_vm=True))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
~~~~~
~~~~~python
        # Topology Lookup
        neighbor_ids = get_neighbors(i, grid_width, grid_width)
        my_neighbors = [channels[nid] for nid in neighbor_ids]
        my_channel = channels[i]

        # Inject the shared resource manager if limits are active
        engine = cs.Engine(
            solver=cs.NativeSolver(),
            executor=cs.LocalExecutor(),
            bus=cs.MessageBus(),
            connector=None,
            resource_manager=shared_resource_manager,
        )
        engine.register(shared_connector_provider)

        agent_workflow = firefly_agent(
            agent_id=i,
            initial_phase=initial_phase,
            period=PERIOD,
            nudge=nudge,
            neighbors=my_neighbors,
            my_channel=my_channel,
            connector=connector,
            refractory_period=period * 0.2,
        )

        # Apply constraints if limit is set
        if concurrency_limit:
            agent_workflow = agent_workflow.with_constraints(cpu_slot=1)

        agent_tasks.append(engine.run(agent_workflow, use_vm=True))

        # Yield every 500 agents to keep UI responsive during setup
        if i > 0 and i % 500 == 0:
~~~~~

~~~~~act
patch_file
observatory/experiments/run_fireflies.py
~~~~~
~~~~~python
if __name__ == "__main__":
    asyncio.run(run_experiment(visualize=True))
~~~~~
~~~~~python
@app.command()
def main(
    visualize: bool = typer.Option(True, help="Enable visualizer UI"),
    agents: int = typer.Option(NUM_AGENTS, help="Number of agents"),
    limit: Optional[int] = typer.Option(None, help="Global concurrency limit (cpu slots)"),
):
    asyncio.run(run_experiment(num_agents=agents, visualize=visualize, concurrency_limit=limit))

if __name__ == "__main__":
    app()
~~~~~

### 下一步建议
现在您可以使用 `python -m observatory.experiments.run_fireflies --limit 100` 来运行实验，并观察是否只有一部分 Agent 能够同时活跃。这验证了 VM 路径、Engine 注入和全局资源共享的集成是否正常工作。
