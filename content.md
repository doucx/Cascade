Excellent. We will now replace the one-off `LocalComputeDelegate` with the persistent `LocalComputeService`, which aligns perfectly with the event-driven, "out-of-process" execution model described in the architecture roadmap.

This is a significant refactoring. We are moving from a model where the Reactor would directly `await` a future from the delegate, to a fire-and-forget model where the Reactor simply places a request on a queue and moves on.

I will generate a plan to perform this replacement.

## [WIP] feat(vm): Implement LocalComputeService for background execution

### 用户需求

实现一个后台服务 `LocalComputeService`，它会持续监听一个入站队列以接收和处理 `ComputeRequest` 对象。同时，废弃并删除旧的 `LocalComputeDelegate` 实现。

### 评论

这是一个关键的架构演进。将 `LocalComputeDelegate` (一个按需调用的异步函数) 升级为 `LocalComputeService` (一个持续运行的后台服务) 是实现“断连式执行 (Disconnected Execution)”的核心。这种模式确保了 Reactor 的主循环永远不会被用户代码的执行所阻塞，因为它只需将计算请求发射到队列中即可，剩下的工作由 `LocalComputeService` 在独立的任务中异步完成。

### 目标

1.  删除 `packages/cascade-vm/src/cascade/vm/compute/local.py` 文件。
2.  创建 `packages/cascade-vm/src/cascade/vm/compute/service.py` 文件。
3.  在新文件中实现 `LocalComputeService` 类，使其包含一个 `run()` 方法来监听和处理来自队列的 `ComputeRequest`。
4.  更新 `packages/cascade-vm/src/cascade/vm/compute/__init__.py` 以导出新实现的 `LocalComputeService`。

### 基本原理

`LocalComputeService` 将被设计为一个长期运行的 `asyncio` 任务。它在其 `__init__` 方法中接收所有必要的依赖（`ObjectStore`, `CodeRegistry`）以及两个关键的队列：一个用于接收请求 (`inbound_queue`)，另一个用于发送结果 (`outbound_queue`)。它的 `run` 方法将构成一个无限循环，持续从 `inbound_queue` 中拉取请求，执行计算（将同步代码委托给线程池），然后将封装好的结果 `Token` 放入 `outbound_queue`，以通知 Reactor 任务已完成。

### 标签

#intent/refine #flow/ready #priority/high #comp/vm #concept/executor #scope/api #scope/core #ai/instruct #task/state/continue

---

### Script

#### Acts 1: 废弃 `LocalComputeDelegate`

首先，我们删除旧的 `LocalComputeDelegate` 实现文件。

~~~~~act
delete_file
packages/cascade-vm/src/cascade/vm/compute/local.py
~~~~~

#### Acts 2: 创建 `LocalComputeService`

现在，我们创建新的 `service.py` 文件并实现 `LocalComputeService`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/compute/service.py
~~~~~
~~~~~python
import asyncio
import inspect
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple, Coroutine

from cascade.spec.physical.object import Ref
from cascade.spec.physical.nodes import Token
from cascade.spec.runtime.storage import ObjectStore
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute.contract import ComputeRequest

logger = logging.getLogger(__name__)


class LocalComputeService:
    """
    A background service that listens for ComputeRequests and executes them locally.
    It embodies the "Data Plane" for a local, in-process execution environment.
    """

    def __init__(
        self,
        store: ObjectStore,
        registry: CodeRegistry,
        inbound_queue: "asyncio.Queue[ComputeRequest]",
        outbound_queue: "asyncio.Queue[Tuple[str, Token]]",
        max_workers: int = None,
    ):
        self.store = store
        self.registry = registry
        self.inbound_queue = inbound_queue
        self.outbound_queue = outbound_queue
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )
        self._running = False

    async def run(self) -> None:
        """
        The main loop of the service. Continuously fetches and processes requests.
        """
        self._running = True
        logger.info("LocalComputeService started.")
        try:
            while self._running:
                request = await self.inbound_queue.get()
                # Create a non-blocking task for each request to allow concurrency
                asyncio.create_task(self._process_request(request))
        finally:
            self._pool.shutdown(wait=False)
            logger.info("LocalComputeService stopped.")

    def stop(self) -> None:
        self._running = False
        # To unblock the `run` loop, we can put a sentinel value,
        # but for now, we assume the managing task will be cancelled.

    async def _process_request(self, request: ComputeRequest) -> None:
        try:
            # 1. Resolve Inputs
            inputs: Dict[str, Any] = {
                key: self.store.get(ref) for key, ref in request.input_refs.items()
            }
            args, kwargs = self._resolve_arguments(inputs)

            # 2. Resolve Code
            func = self.registry.get(request.code_hash)

            # 3. Execute
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._pool, lambda: func(*args, **kwargs)
                )
        except Exception as e:
            logger.exception(f"Computation failed for request on code {request.code_hash}")
            # Per v3.1 spec, exceptions are treated as values
            result = e

        # 4. Store Result and Prepare Token
        result_ref = self.store.put(result)
        result_token = Token(payload=result_ref, trace=request.trace)

        # 5. Report Completion to Outbound Queue
        await self.outbound_queue.put((request.reply_to_nid, result_token))

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        args_map: Dict[int, Any] = {}
        kwargs: Dict[str, Any] = {}

        for k, v in inputs.items():
            if k.isdigit():
                args_map[int(k)] = v
            else:
                kwargs[k] = v

        args: List[Any] = []
        if args_map:
            max_idx = max(args_map.keys())
            args = [None] * (max_idx + 1)
            for idx, val in args_map.items():
                args[idx] = val

        return args, kwargs
~~~~~

#### Acts 3: 更新 `__init__.py` 以导出新服务

最后，我们更新 `__init__.py`，移除对 `LocalComputeDelegate` 的引用，并导出新的 `LocalComputeService`。

~~~~~act
patch_file
packages/cascade-vm/src/cascade/vm/compute/__init__.py
~~~~~
~~~~~python.old
from .local import LocalComputeDelegate
from .contract import ComputeRequest

__all__ = ["LocalComputeDelegate", "ComputeRequest"]
~~~~~
~~~~~python.new
from .contract import ComputeRequest
from .service import LocalComputeService

__all__ = ["ComputeRequest", "LocalComputeService"]
~~~~~

### 下一步建议

我们已经成功地创建了计算服务的核心。现在，我们需要创建一个能向这个服务发送 `ComputeRequest` 的组件。根据路线图，下一步是创建 `standard_dispatcher` 内核函数，它将作为所有用户 `WorkerNode` 在物理层的标准实现，负责将计算任务“发射”到计算队列中。
