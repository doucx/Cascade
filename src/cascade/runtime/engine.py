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
