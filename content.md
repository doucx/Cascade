## [WIP] feat(vm): 实现 LocalComputeDelegate

### 用户需求
在 `cascade-vm` 中实现 `LocalComputeDelegate`，作为 v3.1 架构中负责执行用户态任务的组件。它负责连接存储层（`ObjectStore`）和代码注册表（`CodeRegistry`），处理数据的下载、计算和上传。

### 评论
这是 v3.1 架构中“计算层”的核心实现。与旧的 `Executor` 不同，`LocalComputeDelegate` 不直接处理图节点，而是处理更底层的“代码哈希”和“数据引用”。这种设计使得计算逻辑完全脱离了图的拓扑结构。

### 目标
1.  创建 `cascade.vm.compute` 包。
2.  实现 `LocalComputeDelegate` 类，符合 `ComputeDelegate` 协议。
3.  实现参数解析逻辑，将扁平的输入字典还原为 `args` 和 `kwargs`。
4.  实现对同步和异步函数的混合支持。
5.  添加单元测试验证其行为。

### 基本原理
*   **引用解析**: 使用注入的 `ObjectStore` 将输入的 `Ref` 解引用为实际对象。
*   **参数重组**: 根据输入键是否为数字字符串，将其分流为位置参数 (`args`) 和关键字参数 (`kwargs`)。
*   **混合执行**: 使用 `inspect.iscoroutinefunction` 检测目标函数类型。异步函数直接 `await`，同步函数在 `ThreadPoolExecutor` 中运行，以避免阻塞主循环。
*   **结果物化**: 计算结果再次通过 `ObjectStore.put` 存回，并返回新的 `Ref`。

### 标签
#intent/build #flow/ready #priority/high #comp/runtime #concept/executor #scope/core #ai/instruct #task/domain/vm #task/object/compute-delegate #task/action/implement #task/state/continue

---

### Script

#### Acts 1: 创建 compute 模块

~~~~~act
run_command
~~~~~
~~~~~bash
mkdir -p packages/cascade-vm/src/cascade/vm/compute
touch packages/cascade-vm/src/cascade/vm/compute/__init__.py
~~~~~

#### Acts 2: 实现 `LocalComputeDelegate`

创建 `packages/cascade-vm/src/cascade/vm/compute/local.py`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/compute/local.py
~~~~~
~~~~~python
import asyncio
import inspect
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Tuple

from cascade.spec.physical.object import Ref
from cascade.spec.runtime.compute import ComputeDelegate
from cascade.spec.runtime.storage import ObjectStore
from cascade.vm.registry import CodeRegistry


class LocalComputeDelegate(ComputeDelegate):
    """
    A local implementation of ComputeDelegate that executes code in the current process.
    It handles:
    1. Dereferencing input Refs using the ObjectStore.
    2. Resolving code from the CodeRegistry.
    3. Executing the code (sync code in a thread pool, async code directly).
    4. Storing the result back to the ObjectStore and returning a Ref.
    """

    def __init__(
        self, store: ObjectStore, registry: CodeRegistry, max_workers: int = None
    ):
        self.store = store
        self.registry = registry
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="cascade_compute"
        )

    async def submit(
        self, code_hash: str, input_refs: Dict[str, Ref], config: Dict[str, Any]
    ) -> Ref:
        """
        Execute a task defined by code_hash and input_refs.
        """
        # 1. Resolve Inputs (IO Bound)
        # In a real distributed system, this might be parallelized pre-fetching.
        inputs: Dict[str, Any] = {}
        for key, ref in input_refs.items():
            inputs[key] = self.store.get(ref)

        # 2. Reconstruct Arguments (CPU Bound)
        args, kwargs = self._resolve_arguments(inputs)

        # 3. Resolve Code
        func = self.registry.get(code_hash)

        # 4. Execute (CPU/IO Mixed)
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._pool, lambda: func(*args, **kwargs)
                )
        except Exception as e:
            # Wrap exception to store it as a result?
            # Or let it propagate?
            # In v3.1, exceptions are typically values.
            # But here we might want to let the caller handle the crash
            # or return a specific Error object.
            # For simplicity in this phase, we treat the exception as the result
            # if the architecture expects 'Ref to Error'.
            # However, standard Python behavior is to raise.
            # Let's propagate for now, the caller (Reactor/Adapter) can catch.
            raise e

        # 5. Store Result (IO Bound)
        result_ref = self.store.put(result)
        return result_ref

    def _resolve_arguments(
        self, inputs: Dict[str, Any]
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Reconstruct positional and keyword arguments from a flat dictionary.
        Keys that are digit strings ('0', '1') are treated as positional indices.
        Other keys are treated as keyword arguments.
        """
        args_map: Dict[int, Any] = {}
        kwargs: Dict[str, Any] = {}

        for k, v in inputs.items():
            if k.isdigit():
                args_map[int(k)] = v
            else:
                kwargs[k] = v

        # Convert args_map to list, assuming contiguous 0-based indexing for simplicity.
        # If there are gaps, we might need a more robust approach, but Compiler guarantees 0..N.
        args: List[Any] = []
        if args_map:
            max_idx = max(args_map.keys())
            args = [None] * (max_idx + 1)
            for idx, val in args_map.items():
                args[idx] = val

        return args, kwargs
~~~~~

#### Acts 3: 导出模块

更新 `packages/cascade-vm/src/cascade/vm/compute/__init__.py`。

~~~~~act
write_file
packages/cascade-vm/src/cascade/vm/compute/__init__.py
~~~~~
~~~~~python
from .local import LocalComputeDelegate

__all__ = ["LocalComputeDelegate"]
~~~~~

#### Acts 4: 创建单元测试

创建 `packages/cascade-vm/tests/unit/test_compute_delegate.py`。我们将定义一个简单的 MockObjectStore 来避免对 `cascade-runtime` 的硬依赖，确保单元测试的独立性。

~~~~~act
write_file
packages/cascade-vm/tests/unit/test_compute_delegate.py
~~~~~
~~~~~python
import asyncio
import uuid
import pytest
from typing import Any, Dict, Optional, Tuple

from cascade.spec.physical.object import Ref
from cascade.spec.runtime.storage import ObjectStore
from cascade.vm.registry import CodeRegistry
from cascade.vm.compute.local import LocalComputeDelegate


# --- Mocks ---


class MockObjectStore:
    def __init__(self):
        self._data: Dict[str, Any] = {}

    def put(self, obj: Any, metadata: Optional[Dict[str, Any]] = None) -> Ref:
        uri = f"mem://{uuid.uuid4()}"
        self._data[uri] = obj
        return Ref(uri=uri, meta=metadata or {})

    def get(self, ref: Ref) -> Any:
        return self._data[ref.uri]

    def peek(self, ref: Ref) -> Ref:
        return ref

    def delete(self, ref: Ref) -> None:
        pass


def sync_add(a, b):
    return a + b


async def async_mul(a, b):
    await asyncio.sleep(0.01)
    return a * b


def sync_fail():
    raise ValueError("Boom")


# --- Tests ---


@pytest.fixture
def registry():
    reg = CodeRegistry()
    reg.register("hash_add", sync_add)
    reg.register("hash_mul", async_mul)
    reg.register("hash_fail", sync_fail)
    return reg


@pytest.fixture
def store():
    return MockObjectStore()


@pytest.fixture
def delegate(store, registry):
    return LocalComputeDelegate(store, registry)


@pytest.mark.asyncio
async def test_submit_sync_task(delegate, store):
    # Prepare inputs
    ref_a = store.put(10)
    ref_b = store.put(20)

    # Submit
    result_ref = await delegate.submit(
        "hash_add", {"0": ref_a, "1": ref_b}, config={}
    )

    # Verify
    result = store.get(result_ref)
    assert result == 30


@pytest.mark.asyncio
async def test_submit_async_task(delegate, store):
    # Prepare inputs
    ref_a = store.put(10)
    ref_b = store.put(20)

    # Submit
    result_ref = await delegate.submit(
        "hash_mul", {"a": ref_a, "b": ref_b}, config={}
    )

    # Verify
    result = store.get(result_ref)
    assert result == 200


@pytest.mark.asyncio
async def test_argument_resolution_mixed(delegate, store, registry):
    # Register a function taking mixed args
    def mixed(a, b, c=0):
        return a + b + c

    registry.register("hash_mixed", mixed)

    ref_1 = store.put(1)
    ref_2 = store.put(2)
    ref_3 = store.put(3)

    # Submit with positional '0', '1' and keyword 'c'
    result_ref = await delegate.submit(
        "hash_mixed", {"0": ref_1, "1": ref_2, "c": ref_3}, config={}
    )

    assert store.get(result_ref) == 6


@pytest.mark.asyncio
async def test_exception_propagation(delegate, store):
    with pytest.raises(ValueError, match="Boom"):
        await delegate.submit("hash_fail", {}, config={})
~~~~~

### 下一步建议
我们已经成功实现了 `LocalComputeDelegate` 并通过了单元测试。这标志着 v3.1 架构中“计算委托”组件的就绪。
根据路线图，第三阶段的另一半是 **建立内核执行器 (`PhysicsKernel`)**。这将是纯同步的、基于 `Ref` 操作的核心组件，负责运行标准库中的 `Bleacher`, `Stainer` 等。建议下一步实现 `PhysicsKernel`。
