import time
from typing import Any
from cascade.vm.middleware import Middleware, ExecutionContext, NextHandler
from cascade.runtime.bus import MessageBus
from cascade.runtime.events import (
    TaskExecutionStarted,
    TaskExecutionFinished,
)

class ObservabilityMiddleware(Middleware):
    def __init__(self, bus: MessageBus, run_id: str):
        self.bus = bus
        self.run_id = run_id

    async def handle(self, ctx: ExecutionContext, next_handler: NextHandler) -> Any:
        instr = ctx.instruction
        # Only observe Call/MapCall instructions that represent tasks
        # Jumps are handled by VM loop and are invisible to users
        # Currently Middleware only wraps Call/MapCall dispatch
        
        task_id = getattr(instr, "structure_hash", "unknown")
        task_name = getattr(instr, "task_name", "unknown")

        self.bus.publish(
            TaskExecutionStarted(
                run_id=self.run_id,
                task_id=task_id,
                task_name=task_name
            )
        )

        start_time = time.time()
        status = "Succeeded"
        error_msg = None
        
        try:
            result = await next_handler()
            return result
        except Exception as e:
            status = "Failed"
            error_msg = str(e)
            raise e
        finally:
            duration = time.time() - start_time
            self.bus.publish(
                TaskExecutionFinished(
                    run_id=self.run_id,
                    task_id=task_id,
                    task_name=task_name,
                    status=status,
                    duration=duration,
                    error=error_msg
                )
            )