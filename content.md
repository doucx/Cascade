## [WIP] feat: 集成 Engine 与公共 API，完成 MVP

### 用户需求
执行 Cascade 阶段一 (MVP) 的第 6 步和第 7 步：
1.  **集成引擎**: 创建 `Engine` 类，将 `GraphBuilder`, `Solver`, `Executor`, 和 `MessageBus` 组装成一个完整的工作流。
2.  **公共 API**: 创建并导出 `run()` 门面函数和 `@task` 装饰器。
3.  **验证**: 编写一个端到端的测试用例来验证整个 MVP 的功能。

### 评论
这是 MVP 的最后一步，也是最激动人心的一步。我们将所有独立的、经过测试的组件（模型、构建器、求解器、执行器、总线）像乐高积木一样拼装起来，形成一个有机的整体。`Engine` 是这个系统的大脑，而 `run()` 函数则是用户与之交互的唯一窗口。

### 目标
1.  创建 `src/cascade/runtime/engine.py`。
2.  在 `src/cascade/__init__.py` 中暴露公共 API。
3.  创建 `tests/test_end_to_end.py`。

### 基本原理
*   **Orchestration**: `Engine` 负责协调所有内部组件。它首先构建图，然后求解执行计划，最后遍历计划并调用执行器来运行每个任务，同时通过 `MessageBus` 广播整个过程的状态。
*   **Facade Pattern**: `cascade.run()` 函数是一个门面，它隐藏了 `Engine` 实例化的复杂性，为用户提供了最简单、最直接的入口点。

### 标签
#intent/build #flow/ready #priority/high
#task/domain/runtime #task/object/engine #task/action/integration
#task/state/end #task/status/completed

---

### Script

#### Acts 1: 集成引擎 (Engine)

创建 `Engine` 类，它是所有组件的总指挥。

~~~~~act
write_file
src/cascade/runtime/engine.py
~~~~~
~~~~~python
import time
from typing import Any, Dict, Optional
from uuid import uuid4

from cascade.graph.build import build_graph
from cascade.graph.model import Node
from cascade.spec.task import LazyResult
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import RunStarted, RunFinished, TaskExecutionStarted, TaskExecutionFinished
from cascade.runtime.protocols import Solver, Executor
from cascade.adapters.solvers.native import NativeSolver
from cascade.adapters.executors.local import LocalExecutor

class Engine:
    """
    Orchestrates the entire workflow execution.
    """
    def __init__(
        self,
        solver: Optional[Solver] = None,
        executor: Optional[Executor] = None,
        bus: Optional[MessageBus] = None
    ):
        self.solver = solver or NativeSolver()
        self.executor = executor or LocalExecutor()
        self.bus = bus or MessageBus()

    def run(self, target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
        run_id = str(uuid4())
        start_time = time.time()
        
        # TODO: A proper way to get target names. For now, use the task name.
        target_task_names = [target.task.name]
        
        # Publish start event
        event = RunStarted(run_id=run_id, target_tasks=target_task_names, params=params or {})
        self.bus.publish(event)
        
        try:
            # 1. Build
            graph = build_graph(target)
            
            # 2. Solve
            plan = self.solver.resolve(graph)
            
            # 3. Execute
            results: Dict[str, Any] = {}
            for node in plan:
                task_start_time = time.time()
                
                start_event = TaskExecutionStarted(run_id=run_id, task_id=node.id, task_name=node.name)
                self.bus.publish(start_event)
                
                try:
                    # TODO: Inject params into tasks that need them
                    result = self.executor.execute(node, graph, results)
                    results[node.id] = result
                    
                    task_duration = time.time() - task_start_time
                    finish_event = TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Succeeded",
                        duration=task_duration,
                        result_preview=repr(result)[:100] # Truncate long results
                    )
                    self.bus.publish(finish_event)

                except Exception as e:
                    task_duration = time.time() - task_start_time
                    fail_event = TaskExecutionFinished(
                        run_id=run_id,
                        task_id=node.id,
                        task_name=node.name,
                        status="Failed",
                        duration=task_duration,
                        error=f"{type(e).__name__}: {e}"
                    )
                    self.bus.publish(fail_event)
                    raise # Re-raise to stop the run

            run_duration = time.time() - start_time
            final_event = RunFinished(run_id=run_id, status="Succeeded", duration=run_duration)
            self.bus.publish(final_event)

            return results[target._uuid]

        except Exception as e:
            run_duration = time.time() - start_time
            final_fail_event = RunFinished(
                run_id=run_id,
                status="Failed",
                duration=run_duration,
                error=f"{type(e).__name__}: {e}"
            )
            self.bus.publish(final_fail_event)
            raise

~~~~~

#### Acts 2: 暴露公共 API (Public API)

在 `__init__.py` 中定义 `run` 门面函数并导出 `@task` 和 `Param`。

~~~~~act
write_file
src/cascade/__init__.py
~~~~~
~~~~~python
from typing import Any, Dict, Optional

from .spec.task import task, Param, LazyResult
from .runtime.engine import Engine
from .runtime.bus import MessageBus
from .runtime.subscribers import HumanReadableLogSubscriber

__all__ = ["task", "Param", "run", "LazyResult"]

def run(target: LazyResult, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Runs a Cascade workflow with a default engine configuration.
    
    This is the primary entry point for users. It sets up a default
    engine with a human-readable logger.
    """
    bus = MessageBus()
    # Attach the default logger
    HumanReadableLogSubscriber(bus)
    
    engine = Engine(bus=bus)
    
    return engine.run(target, params=params)
~~~~~

#### Acts 3: 编写端到端测试 (End-to-End Test)

创建一个新测试文件来验证整个流程。

~~~~~act
write_file
tests/test_end_to_end.py
~~~~~
~~~~~python
import pytest
import cascade as cs
import io
import sys
from contextlib import redirect_stdout

def test_e2e_linear_workflow():
    @cs.task
    def get_name():
        return "Cascade"

    @cs.task
    def greet(name: str):
        return f"Hello, {name}!"

    final_greeting = greet(get_name())
    
    output = io.StringIO()
    with redirect_stdout(output):
        result = cs.run(final_greeting)

    assert result == "Hello, Cascade!"
    
    logs = output.getvalue()
    assert "▶️  Starting Run" in logs
    assert "⏳ Running task `get_name`" in logs
    assert "✅ Finished task `get_name`" in logs
    assert "⏳ Running task `greet`" in logs
    assert "✅ Finished task `greet`" in logs
    assert "🏁 Run finished successfully" in logs

def test_e2e_diamond_workflow_and_result():
    @cs.task
    def t_a(): return 5
    @cs.task
    def t_b(x): return x * 2  # 10
    @cs.task
    def t_c(x): return x + 3  # 8
    @cs.task
    def t_d(y, z): return y + z # 18

    r_a = t_a()
    r_b = t_b(r_a)
    r_c = t_c(r_a)
    r_d = t_d(r_b, z=r_c)

    result = cs.run(r_d)
    assert result == 18

def test_e2e_failure_propagation():
    @cs.task
    def ok_task():
        return True

    @cs.task
    def failing_task(x):
        raise ValueError("Something went wrong")

    @cs.task
    def unreachable_task(y):
        return False
    
    r1 = ok_task()
    r2 = failing_task(r1)
    r3 = unreachable_task(r2)

    output = io.StringIO()
    with redirect_stdout(output):
        with pytest.raises(ValueError, match="Something went wrong"):
            cs.run(r3)

    logs = output.getvalue()
    assert "✅ Finished task `ok_task`" in logs
    assert "❌ Failed task `failing_task`" in logs
    assert "💥 Run failed" in logs
    assert "unreachable_task" not in logs
~~~~~

### 下一步建议
**Cascade MVP 已完成！**

我们成功地构建了一个功能完备的“智能脚本执行器”。它拥有优雅的 API、清晰的日志输出，并且核心架构稳固、可扩展。

下一步，我们将进入**阶段二：增强健壮性与可测试性**。
建议的第一个任务是：
*   **实现完整的依赖注入系统 (`@resource`, `cs.inject`)**，这将是 `Cascade` 区别于普通脚本执行器的关键特性，也是解决可测试性问题的核心。
