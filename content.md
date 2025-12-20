好的，收到指令。我将分析你提供的《Cascade 预研计划：原基 (Protoplasm)》文档，识别状态和遗漏，并生成一个计划来完成剩余的工作。

你的分析非常准确。文档显示，“原基”计划的大部分预研工作（第一、二、三、五、六章）都已标记为 `#DONE`，我们已经成功验证了渲染、通信、时序和验证机制的基础能力。

**核心遗漏点正如你所指出的：第四章“压力的具象化 —— 资源约束模拟器”。**

这一章的核心目标是验证 `ConstraintManager` 在高争用环境下的表现，并将其行为可视化。虽然文档中描述了*要做什么*（令牌桶反压测试、阻塞可视化），但尚未提供具体的实验代码和实施方案。

为了完成“原基”计划并为“创世网格”的构建扫清所有障碍，我们必须完成这一最终验证。

我将为你生成一个计划，创建 `bottleneck_sim.py` 实验脚本，以完成第四章的预研目标。

## [WIP] feat: 实现 Protoplasm 第四章的资源约束模拟器

### 用户需求
分析《Cascade 预研计划：原基 (Protoplasm)》的状态，并制定计划以完成其中尚未实现的第四章“资源约束模拟器”。

### 评论
这是“原基”预研计划的最后一项关键任务。验证 `ConstraintManager` 在高并发、高资源争用场景下的稳定性和公平性，对于我们战略学说中“稀缺性作为一种治理手段”的核心理念至关重要。通过将约束状态与 `ForestRenderer` 结合，我们不仅能获得量化指标，还能直观地“看到”系统瓶颈的形成和缓解过程，这将为“创世网格”的物理定律调试提供无价的洞察力。

### 目标
1.  创建一个新的实验脚本 `observatory/protoplasm/governance/bottleneck_sim.py`。
2.  在该脚本中，模拟远超可用资源槽位的 Agent 数量（例如 500 个 Agent 争夺 20 个计算槽位）。
3.  应用一个全局 `concurrency` 约束到所有 Agent 的“工作”任务上。
4.  集成第一章的 `ForestRenderer`，并创建一个 `BottleneckVisualizer` 类，该类订阅 `Engine` 的事件总线。
5.  在可视化界面中，用不同的亮度和颜色区分三种核心状态：
    *   `TaskExecutionStarted`: 正在计算（持有资源槽位）。
    *   `TaskBlocked`: 等待资源（被阻塞）。
    *   `TaskExecutionFinished`: 计算完成（释放资源）。

### 基本原理
我们将创建一个独立的实验脚本。该脚本会：
1.  **设置环境**: 初始化 `ForestRenderer` 用于可视化。
2.  **定义 Agent**: 创建一个简单的、无限递归的 Agent 工作流。该工作流包含一个被约束的核心 `@cs.task(name="agent_i_work")` 和一个驱动循环的 `@cs.task(name="agent_i_loop")`。
3.  **施加约束**: 在 `Engine` 启动前，通过 `engine.constraint_manager.update_constraint()` 方法，施加一个 `type="concurrency"` 的全局约束，其 `scope` 将通过模式匹配（如 `"task:agent_*_work"`）精确地应用到所有 Agent 的工作任务上。
4.  **启动并观测**: 并发启动所有 Agent。同时，`BottleneckVisualizer` 会监听 `Engine` 发出的 `TaskBlocked`、`TaskExecutionStarted` 和 `TaskExecutionFinished` 事件，根据事件类型和 `task_name` 中包含的 Agent ID，实时更新 `ForestRenderer` 状态矩阵中对应单元格的亮度，从而将资源争夺过程动态地呈现在终端上。

### 标签
#intent/build #flow/ready #priority/high #comp/tests #concept/ui #scope/dx #ai/brainstorm #task/domain/testing #task/object/constraint-simulator #task/action/implementation #task/state/begin

---

### Script

#### Acts 1: 创建实验目录

根据计划文档，为第四章的实验创建专用的 `governance` 目录。

~~~~~act
run_command
~~~~~
~~~~~
mkdir -p observatory/protoplasm/governance
~~~~~

#### Acts 2: 编写资源瓶颈模拟器脚本

现在，我们创建 `bottleneck_sim.py` 文件。这个脚本将包含完整的模拟、约束应用和可视化逻辑。

~~~~~act
write_file
observatory/protoplasm/governance/bottleneck_sim.py
~~~~~
~~~~~python
import asyncio
import random
import shutil
import time
from typing import Any

import cascade as cs
from cascade.runtime.events import TaskBlocked, TaskExecutionStarted, TaskExecutionFinished
from cascade.spec.constraint import GlobalConstraint
from observatory.protoplasm.renderer.visualizer_proto import ForestRenderer

# --- Configuration ---
NUM_AGENTS = 500
SLOTS = 20
DURATION = 10.0

# --- Visualizer Logic ---

class BottleneckVisualizer:
    def __init__(self, renderer: ForestRenderer, num_agents: int):
        self.renderer = renderer
        self.grid_width = int(num_agents**0.5) + 1
        
    def get_coords(self, agent_id: int):
        return (agent_id % self.grid_width, agent_id // self.grid_width)

    def handle_event(self, event: Any):
        # We expect task names like "agent_42_work"
        if not hasattr(event, "task_name") or not event.task_name.startswith("agent_"):
            return
            
        try:
            # Format: "agent_{id}_work" or "agent_{id}_loop"
            parts = event.task_name.split("_")
            if len(parts) < 3: return
            agent_id = int(parts[1])
            task_type = parts[2]
            
            x, y = self.get_coords(agent_id)
            
            if task_type == "work":
                if isinstance(event, TaskExecutionStarted):
                    # Acquired Slot = Bright White
                    self.renderer.ingest(x, y, 1.0)
                elif isinstance(event, TaskBlocked):
                    # Waiting for Slot = Mid Cyan
                    self.renderer.ingest(x, y, 0.5)
                elif isinstance(event, TaskExecutionFinished):
                    # Released Slot = Dim
                    self.renderer.ingest(x, y, 0.0)
                    
        except (IndexError, ValueError):
            pass

# --- Agent Definition ---

def make_agent_workflow(i: int):
    # This task simulates the resource-intensive work
    # It will be named "agent_{i}_work" so it matches the constraint "task:agent_*_work"
    @cs.task(name=f"agent_{i}_work")
    async def work(val):
        # Hold the slot for a bit
        await asyncio.sleep(random.uniform(0.1, 0.3))
        return val + 1

    # This task is the recursive driver, it is NOT constrained
    @cs.task(name=f"agent_{i}_loop")
    def loop(val):
        return make_agent_workflow(i)

    return loop(work(0))

# --- Main ---

async def run_simulation():
    # 1. Setup Renderer
    cols, rows = shutil.get_terminal_size()
    render_height = max(10, rows - 4)
    renderer = ForestRenderer(width=cols, height=render_height)
    viz = BottleneckVisualizer(renderer, NUM_AGENTS)
    
    # 2. Setup Engine
    engine_bus = cs.MessageBus()
    engine_bus.subscribe(cs.Event, viz.handle_event)
    
    engine = cs.Engine(
        solver=cs.NativeSolver(),
        executor=cs.LocalExecutor(),
        bus=engine_bus
    )
    
    # 3. Apply Constraint
    # "task:agent_*_work" matches our work tasks
    print(f"Applying constraint: Max {SLOTS} concurrent 'work' tasks...")
    engine.constraint_manager.update_constraint(
        GlobalConstraint(
            id="funnel",
            scope="task:agent_*_work",
            type="concurrency",
            params={"limit": SLOTS}
        )
    )

    # 4. Launch Agents
    # We launch them all on the SAME engine instance
    print(f"Launching {NUM_AGENTS} agents...")
    tasks = []
    for i in range(NUM_AGENTS):
        # We use asyncio.create_task to fire them off
        tasks.append(asyncio.create_task(engine.run(make_agent_workflow(i))))
        
    # 5. Run Visualization
    try:
        renderer_task = asyncio.create_task(renderer.start())
        
        # Let it run for DURATION
        await asyncio.sleep(DURATION)
        
    finally:
        renderer.stop()
        # Cancel all agents
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if not renderer_task.done():
            renderer_task.cancel()
            await renderer_task

if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except KeyboardInterrupt:
        pass
~~~~~

### 下一步建议
1.  **执行测试**: 在项目根目录下运行命令 `python -m observatory.protoplasm.governance.bottleneck_sim` 来启动模拟。
2.  **观察结果**: 你应该能看到一个由字符组成的网格，其中亮点（正在计算）的数量始终被限制在 20 个左右，而其他大量的点（被阻塞）则以较暗的颜色显示，并随着槽位的释放而依次变亮。
3.  **完成预研**: 如果模拟成功，则“原基 (Protoplasm)”预研计划的核心目标就全部达成。我们可以更新计划文档，将第四章也标记为 `#DONE`。
4.  **迈向创世**: 在此之后，我们就拥有了一套经过严格压力测试的“创世开发包 (Genesis SDK)”，可以满怀信心地启动“创世网格”的 Alpha 阶段开发。
